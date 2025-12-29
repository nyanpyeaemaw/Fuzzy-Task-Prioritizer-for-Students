🎯 Fuzzy Task Prioritizer for Students

A Fuzzy Logic–Based Decision Support System

📌 Project Overview

This project implements a Fuzzy Logic System designed to help students prioritize academic tasks effectively.
Instead of using rigid rules, the system applies fuzzy reasoning to handle uncertainty in real-life decision making, such as vague deadlines, subjective importance, and task difficulty.

The system evaluates tasks and produces a priority score and linguistic label (e.g., low, medium, high), enabling students to decide which task to do first.

🧠 Why Fuzzy Logic?

Traditional priority systems rely on fixed thresholds, which do not reflect how humans actually think.
This project uses fuzzy logic because:

Deadlines are often “near” or “far”, not exact

Importance and difficulty are subjective

Human decision-making is approximate, not binary

Fuzzy logic allows smoother, more realistic prioritization.

🔢 Input Variables

The system takes three inputs:

Deadline Proximity

Measured in days (0–30)

Linguistic values: close, moderate, far

Task Importance

Scale: 0–10

Linguistic values: low, medium, high

Task Difficulty

Scale: 0–10

Linguistic values: easy, moderate, hard

📤 Output Variable

Task Priority

Numeric score: 0–100

Linguistic labels:

very low

low

medium

high

very high

⚙️ System Design
Membership Functions

Trapezoidal and triangular membership functions are used

Overlapping ranges allow smooth transitions between priority levels

Rule Base

A carefully selected subset of fuzzy rules is defined

Rules combine urgency, importance, and difficulty

Full rule explosion (135 rules) is avoided while maintaining coverage

Example rule:

IF deadline is close AND importance is high
THEN priority is very high

🛠️ Technologies & Libraries

Programming Language: Python

Fuzzy Logic Library: scikit-fuzzy

Numerical Computing: NumPy

Environment: Desktop (Windows/Linux)

🚀 How to Run

Clone the repository:

git clone https://github.com/your-username/your-repo-name.git


Install required libraries:

pip install numpy scikit-fuzzy


Run the fuzzy logic module:

python fuzzylogic.py

📂 Project Structure
├── fuzzylogic.py     # Fuzzy logic system and rules
├── main.py           # Task prioritization interface / integration
├── README.md         # Project documentation

📊 Example Output
{
  'score': 82.15,
  'label': 'very high',
  'inputs': {
    'days_to_deadline': 3,
    'importance': 9,
    'difficulty': 7
  }
}

📚 Learning Outcomes

Practical understanding of Fuzzy Inference Systems

Design of membership functions and rule bases

Application of fuzzy logic to real-world problems

Improved decision-making system design

Team-based software development experience

👥 Contributors

Nyan Pyae Maw

Min Sett Paing

Akeri Myint Zaw

Su Myat Wai

📜 License

This project is developed for educational purposes as part of a Fuzzy Logic / Artificial Intelligence course.
All rights reserved by the contributors.
