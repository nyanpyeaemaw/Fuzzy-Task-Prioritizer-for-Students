import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


# ----------------------------
# Universes (input/output ranges)
# ----------------------------
deadline_days = ctrl.Antecedent(np.arange(0, 31, 1), 'deadline_days')  # 0–30 days
importance = ctrl.Antecedent(np.arange(0, 11, 1), 'importance')        # 0–10
difficulty = ctrl.Antecedent(np.arange(0, 11, 1), 'difficulty')        # 0–10

priority = ctrl.Consequent(np.arange(0, 101, 1), 'priority')           # 0–100

# ----------------------------
# Membership functions
# ----------------------------

# notes
# 27 (inputs)×5 (outputs)=135 possible rules
# no need to put all 135 combinations
# can define a smaller subset that captures the logic
# the system can produce results cuz membership functions overlaps

# Deadline proximity
deadline_days['close']    = fuzz.trapmf(deadline_days.universe, [0, 0, 1, 3])
deadline_days['moderate'] = fuzz.trimf(deadline_days.universe,  [2, 7, 14])
deadline_days['far']      = fuzz.trapmf(deadline_days.universe, [10, 20, 30, 30])

# Importance
importance['low']    = fuzz.trapmf(importance.universe, [0, 0, 2, 4])
importance['medium'] = fuzz.trimf(importance.universe,  [3, 5, 7])
importance['high']   = fuzz.trapmf(importance.universe, [6, 8, 10, 10])

# Difficulty
difficulty['easy']    = fuzz.trapmf(difficulty.universe, [0, 0, 2, 4])
difficulty['moderate'] = fuzz.trimf(difficulty.universe,  [3, 5, 7])
difficulty['hard']     = fuzz.trapmf(difficulty.universe, [6, 8, 10, 10])

# Output: Priority
priority['very_low']  = fuzz.trapmf(priority.universe, [0, 0, 10, 25])
priority['low']       = fuzz.trimf(priority.universe,  [15, 30, 45])
priority['medium']    = fuzz.trimf(priority.universe,  [35, 50, 65])
priority['high']      = fuzz.trimf(priority.universe,  [55, 70, 85])
priority['very_high'] = fuzz.trapmf(priority.universe, [75, 90, 100, 100])

# ----------------------------
# Rules
# ----------------------------
rules = [
    # Urgency + importance dominate
    ctrl.Rule(deadline_days['close'] & importance['high'], priority['very_high']),
    ctrl.Rule(deadline_days['close'] & importance['medium'], priority['high']),
    ctrl.Rule(deadline_days['moderate'] & importance['high'], priority['high']),
    ctrl.Rule(deadline_days['far'] & importance['high'] & difficulty['hard'], priority['high']),
    ctrl.Rule(deadline_days['far'] & importance['high'] & difficulty['easy'], priority['medium']),

    # Low importance tends to reduce priority
    ctrl.Rule(deadline_days['far'] & importance['low'], priority['very_low']),
    ctrl.Rule(deadline_days['moderate'] & importance['low'], priority['low']),
    ctrl.Rule(deadline_days['close'] & importance['low'], priority['medium']),

    # Difficulty tweaks
    ctrl.Rule(deadline_days['close'] & importance['high'] & difficulty['hard'], priority['very_high']),
    ctrl.Rule(deadline_days['close'] & importance['medium'] & difficulty['easy'], priority['high']),
    ctrl.Rule(deadline_days['moderate'] & importance['medium'], priority['medium']),
    ctrl.Rule(difficulty['hard'] & importance['low'] & deadline_days['far'], priority['very_low']),
    ctrl.Rule(difficulty['easy'] & importance['medium'] & deadline_days['far'], priority['low']),

    
    # Coverage rules to avoid no-fire situations
    ctrl.Rule(deadline_days['far'] & importance['high'], priority['high']),
    ctrl.Rule(deadline_days['moderate'] & importance['high'], priority['high']),  # already present, keeps coverage
    ctrl.Rule(deadline_days['far'] & importance['medium'] & difficulty['moderate'], priority['low']),
  
]

# Build the control system
priority_ctrl = ctrl.ControlSystem(rules)
priority_engine = ctrl.ControlSystemSimulation(priority_ctrl)

# ----------------------------
# Helper: crisp score -> label
# ----------------------------
def _label_for_priority(score: float) -> str:
    # Compute membership strengths at the crisp score and pick the max label
    memberships = {
        'very low': fuzz.interp_membership(priority.universe, priority['very_low'].mf, score),
        'low':      fuzz.interp_membership(priority.universe, priority['low'].mf, score),
        'medium':   fuzz.interp_membership(priority.universe, priority['medium'].mf, score),
        'high':     fuzz.interp_membership(priority.universe, priority['high'].mf, score),
        'very high':fuzz.interp_membership(priority.universe, priority['very_high'].mf, score),
    }
    return max(memberships.items(), key=lambda x: x[1])[0]

# ----------------------------
# Public API
# ----------------------------
def prioritize_task(days_to_deadline: float, importance_score: float, difficulty_score: float):
    """
    Args:
        days_to_deadline: 0..30 (smaller = more urgent)
        importance_score: 0..10
        difficulty_score: 0..10

    Returns:
        dict with fields:
            - score: float in [0,100]
            - label: 'very low'|'low'|'medium'|'high'|'very high'
            - inputs: echo of normalized inputs
    """
    # Clamp inputs to universe ranges
    d = np.clip(days_to_deadline, deadline_days.universe.min(), deadline_days.universe.max())
    im = np.clip(importance_score, importance.universe.min(), importance.universe.max())
    df = np.clip(difficulty_score, difficulty.universe.min(), difficulty.universe.max())

    priority_engine.input['deadline_days'] = float(d)
    priority_engine.input['importance'] = float(im)
    priority_engine.input['difficulty'] = float(df)

    # Compute
    priority_engine.compute()
    score = float(priority_engine.output['priority'])
    label = _label_for_priority(score)

    return {
        'score': round(score, 2),
        'label': label,
        'inputs': {
            'days_to_deadline': float(d),
            'importance': float(im),
            'difficulty': float(df),
        }
    }

# ----------------------------
# Example usage
# ----------------------------
if __name__ == "__main__":
    example = prioritize_task(days_to_deadline=30, importance_score=1, difficulty_score=1)
    print(example)  # e.g., {'score': 82.15, 'label': 'very high', 'inputs': {...}}

    # Results
    # lowest score -> 9.29
    # highest score -> 90.71