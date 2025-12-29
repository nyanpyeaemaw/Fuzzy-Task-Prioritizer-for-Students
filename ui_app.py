# ui_app.py
import os, json, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# ---- Your modules ----
import fuzzylogic as fl                     # fuzzy scoring (0..100) + label  :contentReference[oaicite:3]{index=3}
import main as ai                           # Groq LLM / tasks json loader     :contentReference[oaicite:4]{index=4}

TASKS_PATH = "tasks.json"                   # your shared storage              :contentReference[oaicite:5]{index=5}

# ---------- JSON I/O ----------
def _ensure_tasks_file():
    if not os.path.exists(TASKS_PATH):
        with open(TASKS_PATH, "w", encoding="utf-8") as f:
            json.dump({"tasks": []}, f, ensure_ascii=False, indent=2)

def load_tasks_raw():
    """Load exactly as stored on disk (dict with 'tasks')."""
    _ensure_tasks_file()
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        # normalize old shape into object
        data = {"tasks": data}
    data.setdefault("tasks", [])
    return data

def save_tasks_raw(data_obj):
    """Persist canonical object {'tasks': [...]}."""
    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data_obj, f, ensure_ascii=False, indent=2)

# ---------- Helpers ----------
def _deadline_bucket(days: float) -> str:
    if days <= 3: return "close"
    if days <= 14: return "moderate"
    return "far"

def _short(s: str, n=60):
    if not s: return ""
    return s if len(s) <= n else s[:n] + "…"

def _recompute_priority(days: float, imp: float, diff: float):
    """Run your fuzzy engine and return (score,label)."""
    res = fl.prioritize_task(days_to_deadline=days, importance_score=imp, difficulty_score=diff)  # :contentReference[oaicite:6]{index=6}
    return float(res["score"]), str(res["label"])

def _normalize_for_llm():
    """
    Use ai.load_tasks_from_json to get a normalized list the LLM expects:
    each item has strings + priority_score/priority_label.              :contentReference[oaicite:7]{index=7}
    """
    try:
        return ai.load_tasks_from_json(TASKS_PATH)  # tolerant to many shapes  :contentReference[oaicite:8]{index=8}
    except Exception:
        # last-resort fallback if json temporarily invalid
        obj = load_tasks_raw()
        lst = []
        for t in obj["tasks"]:
            lst.append({
                "name": t.get("name") or t.get("task_name") or "(no name)",
                "deadline": t.get("deadline") or t.get("deadline_proximity") or "moderate",
                "importance": t.get("importance","medium"),
                "difficulty": t.get("difficulty","moderate"),
                "priority_label": t.get("priority_label") or (t.get("priority",{}) or {}).get("label"),
                "priority_score": t.get("priority_score") or (t.get("priority",{}) or {}).get("score"),
            })
        return lst

# ---------- Tk App ----------
root = tk.Tk()
root.title("Fuzzy Task Prioritizer + Chatbot")
root.geometry("1120x680")
root.minsize(980, 560)
root.grid_columnconfigure(1, weight=1); root.grid_rowconfigure(0, weight=1)

sidebar = tk.Frame(root, bg="#2f3236", width=210); sidebar.grid(row=0, column=0, sticky="ns"); sidebar.grid_propagate(False)
main = tk.Frame(root, bg="white"); main.grid(row=0, column=1, sticky="nsew")
page_tasks = tk.Frame(main, bg="white"); page_add = tk.Frame(main, bg="white"); page_chat = tk.Frame(main, bg="white")
for p in (page_tasks, page_add, page_chat): p.grid(row=0, column=0, sticky="nsew")
main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=1)

def switch(page):
    for p in (page_tasks, page_add, page_chat): p.grid_remove()
    page.grid()

def mk_btn(text, cmd):
    return tk.Button(sidebar, text=text, fg="white", bg="#43464b", activebackground="#52565c",
                     relief="flat", padx=12, pady=10, command=cmd)

mk_btn("Tasks",   lambda: (refresh_table(), switch(page_tasks))).pack(fill="x", padx=14, pady=(16, 8))
mk_btn("Add Task",lambda: switch(page_add)).pack(fill="x", padx=14, pady=8)
mk_btn("Chatbot", lambda: switch(page_chat)).pack(fill="x", padx=14, pady=8)

# ====== Tasks Page ======
tk.Label(page_tasks, text="All Tasks (from tasks.json)", font=("Segoe UI", 16, "bold"), bg="white")\
  .pack(anchor="w", padx=16, pady=(12, 6))

bar = tk.Frame(page_tasks, bg="white"); bar.pack(fill="x", padx=16, pady=(0, 8))
btn_refresh = tk.Button(bar, text="Reload", width=10)
btn_edit = tk.Button(bar, text="Edit", width=10)
btn_delete = tk.Button(bar, text="Delete", width=10)
btn_export = tk.Button(bar, text="Export CSV", width=12)
for i, b in enumerate((btn_refresh, btn_edit, btn_delete, btn_export)):
    b.pack(side="left", padx=(0 if i==0 else 8,0))

columns = ("name","deadline","importance","difficulty","score","label","notes")
tree = ttk.Treeview(page_tasks, columns=columns, show="headings", height=18)
for col, w in zip(columns, (220,100,120,120,80,110,320)):
    tree.heading(col, text=col.capitalize()); tree.column(col, width=w, anchor="w")
vsb = ttk.Scrollbar(page_tasks, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=vsb.set)
tree.pack(side="left", fill="both", expand=True, padx=(16,0), pady=(0,16))
vsb.pack(side="left", fill="y", padx=(0,16), pady=(0,16))

def refresh_table():
    tree.delete(*tree.get_children())
    obj = load_tasks_raw()
    for t in obj["tasks"]:
        # Extract score/label stored under either flat keys or nested priority
        pr = t.get("priority", {})
        score = t.get("priority_score") or (pr.get("score") if isinstance(pr, dict) else (pr if isinstance(pr,(int,float)) else None))
        label = t.get("priority_label") or (pr.get("label") if isinstance(pr, dict) else (pr if isinstance(pr,str) else None))
        tree.insert("", "end", values=(
            t.get("name") or t.get("task_name") or "(no name)",
            t.get("deadline") or t.get("deadline_proximity") or "moderate",
            t.get("importance","medium"),
            t.get("difficulty","moderate"),
            f"{float(score):.2f}" if score is not None else "-",
            label or "-",
            _short(t.get("notes",""))
        ))

def delete_selected():
    sel = tree.selection()
    if not sel: return messagebox.showinfo("Delete", "Select a row first.")
    name = tree.item(sel[0])["values"][0]
    if not messagebox.askyesno("Confirm", f"Delete '{name}'?"): return
    obj = load_tasks_raw()
    obj["tasks"] = [t for t in obj["tasks"] if (t.get("name") or t.get("task_name")) != name]
    save_tasks_raw(obj); refresh_table()

def open_edit():
    sel = tree.selection()
    if not sel: return messagebox.showinfo("Edit", "Select a row first.")
    vals = tree.item(sel[0])["values"]
    current_name = vals[0]

    # locate in json
    obj = load_tasks_raw()
    t = None
    for it in obj["tasks"]:
        nm = it.get("name") or it.get("task_name")
        if nm == current_name:
            t = it; break
    if t is None: return messagebox.showerror("Error", "Task not found in JSON.")

    # derive numeric for edit
    # keep previous numeric hints if present; otherwise estimate
    days = float(t.get("days", 7))
    imp = float(t.get("importance10", 5))
    diff= float(t.get("difficulty10", 5))
    if "days" not in t:
        # guess from deadline bucket
        d = (t.get("deadline") or t.get("deadline_proximity") or "moderate")
        days = 2 if d=="close" else 7 if d=="moderate" else 20

    win = tk.Toplevel(root); win.title(f"Edit – {current_name}"); win.geometry("420x300")

    def row(lbl):
        fr = tk.Frame(win); fr.pack(fill="x", padx=14, pady=6); tk.Label(fr, text=lbl, width=16, anchor="w").pack(side="left"); return fr
    r1=row("Task Name"); e_name=tk.Entry(r1, width=28); e_name.pack(side="left"); e_name.insert(0, current_name)
    r2=row("Days (0–30)"); s_days=tk.Spinbox(r2, from_=0, to=30, width=6); s_days.pack(side="left"); s_days.delete(0,"end"); s_days.insert(0, str(int(days)))
    r3=row("Importance (0–10)"); s_imp=tk.Spinbox(r3, from_=0, to=10, width=6); s_imp.pack(side="left"); s_imp.delete(0,"end"); s_imp.insert(0, str(int(imp)))
    r4=row("Difficulty (0–10)"); s_diff=tk.Spinbox(r4, from_=0, to=10, width=6); s_diff.pack(side="left"); s_diff.delete(0,"end"); s_diff.insert(0, str(int(diff)))
    r5=row("Notes"); e_notes=tk.Entry(r5, width=28); e_notes.pack(side="left"); e_notes.insert(0, t.get("notes",""))

    def save_edit():
        try:
            name = e_name.get().strip()
            days = float(s_days.get()); imp=float(s_imp.get()); dif=float(s_diff.get())
            score, label = _recompute_priority(days, imp, dif)  # fuzzy  :contentReference[oaicite:9]{index=9}
            # update object
            t.clear()
            t.update({
                "name": name,
                "deadline": _deadline_bucket(days),
                "importance": "high" if imp>=7 else "medium" if imp>=4 else "low",
                "difficulty": "hard" if dif>=7 else "moderate" if dif>=4 else "easy",
                "days": days, "importance10": imp, "difficulty10": dif,
                "priority": {"score": score, "label": label},   # stored canonical
                "priority_score": score, "priority_label": label,  # redundant, good for compatibility  :contentReference[oaicite:10]{index=10}
                "notes": e_notes.get().strip()
            })
            save_tasks_raw(obj); refresh_table(); win.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    tk.Button(win, text="Save", width=10, command=save_edit).pack(pady=8)

btn_refresh.config(command=refresh_table)
btn_delete.config(command=delete_selected)
btn_edit.config(command=open_edit)

def export_csv():
    path = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
    if not path: return
    import csv
    obj = load_tasks_raw()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name","deadline","importance","difficulty","priority_score","priority_label","notes"])
        for t in obj["tasks"]:
            pr=t.get("priority",{})
            score=t.get("priority_score") or (pr.get("score") if isinstance(pr,dict) else (pr if isinstance(pr,(int,float)) else None))
            label=t.get("priority_label") or (pr.get("label") if isinstance(pr,dict) else (pr if isinstance(pr,str) else None))
            w.writerow([
                t.get("name") or t.get("task_name") or "",
                t.get("deadline") or t.get("deadline_proximity") or "",
                t.get("importance",""),
                t.get("difficulty",""),
                f"{float(score):.2f}" if score is not None else "",
                label or "",
                t.get("notes","")
            ])
    messagebox.showinfo("Export", f"Saved to {path}")
btn_export.config(command=export_csv)

# ====== Add Task Page ======
tk.Label(page_add, text="Add Task (calculates & saves into tasks.json)", font=("Segoe UI", 16, "bold"), bg="white")\
  .pack(anchor="w", padx=16, pady=12)

form = tk.Frame(page_add, bg="white"); form.pack(anchor="nw", padx=16, pady=6)
def row(lbl): fr=tk.Frame(form, bg="white"); fr.pack(fill="x", pady=6); tk.Label(fr, text=lbl, width=16, anchor="w", bg="white").pack(side="left"); return fr
r1=row("Task Name"); e_name=tk.Entry(r1, width=40); e_name.pack(side="left")
r2=row("Days to deadline"); s_days=tk.Spinbox(r2, from_=0, to=30, width=6); s_days.pack(side="left"); s_days.delete(0,"end"); s_days.insert(0,"3")
r3=row("Importance (0–10)"); s_imp=tk.Spinbox(r3, from_=0, to=10, width=6); s_imp.pack(side="left"); s_imp.delete(0,"end"); s_imp.insert(0,"8")
r4=row("Difficulty (0–10)"); s_diff=tk.Spinbox(r4, from_=0, to=10, width=6); s_diff.pack(side="left"); s_diff.delete(0,"end"); s_diff.insert(0,"5")
r5=row("Notes"); e_notes=tk.Entry(r5, width=40); e_notes.pack(side="left")

status = tk.Label(page_add, text="", fg="#555", bg="white"); status.pack(anchor="w", padx=16, pady=6)

def add_task():
    name = e_name.get().strip()
    if not name: return messagebox.showwarning("Missing", "Please enter task name.")
    try:
        days=float(s_days.get()); imp=float(s_imp.get()); dif=float(s_diff.get())
        score, label = _recompute_priority(days, imp, dif)  # fuzzy calc  :contentReference[oaicite:11]{index=11}
        obj = load_tasks_raw()
        obj["tasks"].append({
            "name": name,
            "deadline": _deadline_bucket(days),                # for LLM context  :contentReference[oaicite:12]{index=12}
            "importance": "high" if imp>=7 else "medium" if imp>=4 else "low",
            "difficulty": "hard" if dif>=7 else "moderate" if dif>=4 else "easy",
            "days": days, "importance10": imp, "difficulty10": dif,
            "priority": {"score": score, "label": label},     # canonical
            "priority_score": score, "priority_label": label, # compatibility  :contentReference[oaicite:13]{index=13}
            "notes": e_notes.get().strip()
        })
        save_tasks_raw(obj)
        status.config(text=f"Saved: {name} (Priority {label} – {score:.2f})")
        e_name.delete(0,"end"); e_notes.delete(0,"end")
    except Exception as e:
        messagebox.showerror("Error", f"Could not add task:\n{e}")

btns = tk.Frame(page_add, bg="white"); btns.pack(anchor="w", padx=16, pady=6)
tk.Button(btns, text="Add", width=12, command=add_task).pack(side="left")
tk.Button(btns, text="Clear", width=10,
          command=lambda:(e_name.delete(0,"end"), s_days.delete(0,"end"), s_days.insert(0,"3"),
                          s_imp.delete(0,"end"), s_imp.insert(0,"8"),
                          s_diff.delete(0,"end"), s_diff.insert(0,"5"),
                          e_notes.delete(0,"end"), status.config(text=""))).pack(side="left", padx=8)

# ====== Chat Page (uses Groq LLM in main.py) ======
tk.Label(page_chat, text="Chatbot (Groq Llama via main.py)", font=("Segoe UI", 16, "bold"), bg="white")\
  .pack(anchor="w", padx=16, pady=12)

chat_box = ScrolledText(page_chat, wrap="word", height=22, state="disabled"); chat_box.pack(fill="both", expand=True, padx=16)
chat_box.tag_configure("You", font=("Segoe UI",10,"bold")); chat_box.tag_configure("Bot", font=("Segoe UI",10,"bold"), foreground="#1f6feb")

bar = tk.Frame(page_chat, bg="white"); bar.pack(fill="x", padx=16, pady=12)
entry = tk.Entry(bar, font=("Segoe UI",11)); entry.pack(side="left", fill="x", expand=True, ipady=6)
send_btn = tk.Button(bar, text="Send", width=10); send_btn.pack(side="left", padx=(8,0))
typing_lbl = tk.Label(page_chat, text="", fg="#666", bg="white"); typing_lbl.pack(anchor="w", padx=16, pady=(0, 10))

def chat_add(role, text):
    ts = datetime.now().strftime("%H:%M")
    chat_box.configure(state="normal")
    chat_box.insert("end", f"{role} ({ts}):\n", role)
    chat_box.insert("end", text + "\n\n")
    chat_box.configure(state="disabled"); chat_box.see("end")

def _chat_worker(msg):
    try:
        tasks_for_llm = _normalize_for_llm()      # consistent schema for LLM  :contentReference[oaicite:14]{index=14}
        reply_blob = ai.chatbot_reply(msg, tasks_for_llm)  # calls Groq with your system prompt  :contentReference[oaicite:15]{index=15}
        reply = reply_blob.get("reply","(no reply)")
    except Exception as e:
        reply = f"LLM error: {e}"
    finally:
        root.after(0, lambda: (chat_add("Bot", reply), typing_lbl.config(text=""), send_btn.config(state="normal")))

def send_msg(event=None):
    msg = entry.get().strip()
    if not msg: return
    entry.delete(0,"end"); chat_add("You", msg)
    send_btn.config(state="disabled"); typing_lbl.config(text="Bot is typing…")
    threading.Thread(target=_chat_worker, args=(msg,), daemon=True).start()

send_btn.config(command=send_msg); entry.bind("<Return>", send_msg)

def reset_chat():
    ai.reset_chat_history()  # optional helper in main.py  :contentReference[oaicite:16]{index=16}
    chat_box.configure(state="normal"); chat_box.delete("1.0", "end"); chat_box.configure(state="disabled")
    chat_add("Bot", "Session reset. Ask me which task to do first!")
tk.Button(page_chat, text="Reset Chat", command=reset_chat).pack(anchor="e", padx=16, pady=(0, 8))

# start
refresh_table(); switch(page_tasks)
chat_add("Bot", "Hi! Add tasks on the Add Task page. The Tasks panel reads from tasks.json; the chatbot uses your Groq model.")

root.mainloop()
