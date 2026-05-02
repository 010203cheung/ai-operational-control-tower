# app.py
# Hugging Face / Gradio demo for ai-operational-control-tower

import hashlib
from datetime import datetime

import gradio as gr
import joblib
import pandas as pd

# =========================
# 1. Load Models
# =========================
demand_model = joblib.load("demand_model.joblib")
risk_model = joblib.load("operational_risk_model.joblib")
maintenance_model = joblib.load("maintenance_model.joblib")
FEATURES = joblib.load("features.joblib")

# =========================
# 2. Shared State + Logs
# =========================
shared_state = {}
decision_logs = []

# =========================
# 2B. RAG-lite Knowledge Base
# =========================
# RAG-lite: rule-based retrieval from a structured knowledge base.
# Future upgrade: replace this with vector database + semantic retrieval
# from healthcare SOPs, appointment policies, equipment maintenance guides,
# escalation protocols, and operational playbooks.
SUPPORT_KB = {
    "high_operational_risk": {
        "question": "What should we do if operational risk is high?",
        "answer": "Review the schedule, confirm critical appointments, and prepare contingency resources before operations begin."
    },
    "high_maintenance_risk": {
        "question": "What should we do if equipment maintenance risk is high?",
        "answer": "Avoid assigning high-risk equipment to critical workflows. Prepare backup equipment or schedule inspection."
    },
    "high_demand": {
        "question": "What should we do if predicted workload is high?",
        "answer": "Prepare additional staffing capacity, monitor department congestion, and prioritize critical cases."
    },
    "high_overall_risk": {
        "question": "What should we do if overall operational risk is high?",
        "answer": "Escalate to operations lead for review and coordinate preventive actions before execution."
    },
    "normal_operations": {
        "question": "What if all risks are low?",
        "answer": "Proceed with normal operations while continuing routine monitoring."
    }
}

# =========================
# 3. Build Input DataFrame
# =========================
# Note:
# The model uses healthcare-style operational feature names.
# In a real deployment, these features would be collected from scheduling,
# department workload, equipment maintenance, and staffing systems.
def build_input_df(
    workflow_complexity,
    num_cases,
    department_congestion,
    queue_intensity,
    external_disruption,
    equipment_usage_level,
    days_since_maintenance,
    staff_experience,
    current_resource_utilization,
):
    input_df = pd.DataFrame([{
        "workflow_complexity": workflow_complexity,
        "num_cases": num_cases,
        "department_congestion": department_congestion,
        "queue_intensity": queue_intensity,
        "external_disruption": external_disruption,
        "equipment_usage_level": equipment_usage_level,
        "days_since_maintenance": days_since_maintenance,
        "staff_experience": staff_experience,
        "current_resource_utilization": current_resource_utilization,
    }])

    return input_df[FEATURES]

# =========================
# 4. Specialist Agents
# =========================
# This section simulates a simplified multi-agent AI architecture.
# Each agent is responsible for one operational decision-support task.
def demand_agent(input_df):
    demand = demand_model.predict(input_df)[0]
    shared_state["demand_agent"] = {
        "predicted_workload": round(float(demand), 2)
    }
    return demand

def operational_risk_agent(input_df):
    risk_prob = risk_model.predict_proba(input_df)[0][1]
    shared_state["operational_risk_agent"] = {
        "operational_risk_probability": round(float(risk_prob), 3)
    }
    return risk_prob

def maintenance_agent(input_df):
    maintenance_prob = maintenance_model.predict_proba(input_df)[0][1]
    shared_state["maintenance_agent"] = {
        "equipment_risk_probability": round(float(maintenance_prob), 3)
    }
    return maintenance_prob

def support_agent(demand, risk_prob, maintenance_prob, final_risk):
    retrieved_answers = []

    if demand >= 150:
        retrieved_answers.append(SUPPORT_KB["high_demand"]["answer"])

    if risk_prob >= 0.5:
        retrieved_answers.append(SUPPORT_KB["high_operational_risk"]["answer"])

    if maintenance_prob >= 0.5:
        retrieved_answers.append(SUPPORT_KB["high_maintenance_risk"]["answer"])

    if final_risk >= 0.7:
        retrieved_answers.append(SUPPORT_KB["high_overall_risk"]["answer"])

    if not retrieved_answers:
        retrieved_answers.append(SUPPORT_KB["normal_operations"]["answer"])

    shared_state["support_agent"] = {"retrieved_guidance": retrieved_answers}
    return retrieved_answers

def explain_agent(input_df):
    explanations = []
    row = input_df.iloc[0]

    if row["queue_intensity"] > 0.7:
        explanations.append("High queue intensity may increase delay or scheduling risk.")

    if row["department_congestion"] > 0.75:
        explanations.append("High department congestion may slow down patient or workflow processing.")

    if row["external_disruption"] == 1:
        explanations.append("External disruption flag is active, which may affect operations.")

    if row["equipment_usage_level"] > 160000:
        explanations.append("High equipment usage level may increase failure probability.")

    if row["days_since_maintenance"] > 120:
        explanations.append("Overdue maintenance increases equipment reliability risk.")

    if row["current_resource_utilization"] > 70:
        explanations.append("High resource utilization increases operational strain.")

    if not explanations:
        explanations.append("No significant risk factors detected.")

    shared_state["explain_agent"] = {"explanations": explanations}
    return explanations

# =========================
# 5. Control Tower Agent
# =========================
# The Control Tower combines outputs from multiple agents
# to produce coordinated operational recommendations.
def control_tower_agent(demand, risk_prob, maintenance_prob):
    recommendations = []

    final_risk = (
        0.4 * risk_prob
        + 0.4 * maintenance_prob
        + 0.2 * min(demand / 250, 1)
    )

    if demand >= 150:
        recommendations.append("Prepare additional operational capacity.")

    if risk_prob >= 0.5:
        recommendations.append("High operational risk — review schedule and confirm critical cases.")

    if maintenance_prob >= 0.5:
        recommendations.append("Equipment risk detected — prepare backup equipment or inspection.")

    if final_risk >= 0.7:
        recommendations.append("Overall risk is high — assign operations lead review.")

    if not recommendations:
        recommendations.append("Proceed with normal operations.")

    shared_state["control_tower_agent"] = {
        "final_risk_score": round(float(final_risk), 3),
        "recommendations": recommendations,
    }

    return final_risk, recommendations

# =========================
# 6. Master Orchestrator
# =========================
def run_control_tower_system(
    workflow_complexity,
    num_cases,
    department_congestion,
    queue_intensity,
    external_disruption,
    equipment_usage_level,
    days_since_maintenance,
    staff_experience,
    current_resource_utilization,
):
    shared_state.clear()

    input_df = build_input_df(
        workflow_complexity,
        num_cases,
        department_congestion,
        queue_intensity,
        external_disruption,
        equipment_usage_level,
        days_since_maintenance,
        staff_experience,
        current_resource_utilization,
    )

    demand = demand_agent(input_df)
    risk_prob = operational_risk_agent(input_df)
    maintenance_prob = maintenance_agent(input_df)

    final_risk, recommendations = control_tower_agent(
        demand,
        risk_prob,
        maintenance_prob,
    )

    support_guidance = support_agent(
        demand,
        risk_prob,
        maintenance_prob,
        final_risk,
    )

    explanations = explain_agent(input_df)

    result = {
        "predicted_workload": round(float(demand), 2),
        "operational_risk_probability": round(float(risk_prob), 3),
        "equipment_risk_probability": round(float(maintenance_prob), 3),
        "final_risk_score": round(float(final_risk), 3),
        "recommendations": recommendations,
        "support_guidance": support_guidance,
        "explanations": explanations,
        "shared_state": shared_state.copy(),
    }

    decision_logs.append(result)
    return result

# =========================
# 6B. Pretty UI Formatter
# =========================
def get_risk_level(risk_score):
    if risk_score >= 0.7:
        return "🔴 High"
    if risk_score >= 0.4:
        return "🟡 Moderate"
    return "🟢 Low"

def format_control_tower_report(result):
    risk_level = get_risk_level(result["final_risk_score"])

    recommendations = "\n".join([f"- {item}" for item in result["recommendations"]])
    guidance = "\n".join([f"- {item}" for item in result["support_guidance"]])
    explanations = "\n".join([f"- {item}" for item in result["explanations"]])

    return f"""
## 🧠 Operational Control Tower Summary

| Metric | Result |
|---|---:|
| 📊 Predicted Workload | **{result["predicted_workload"]}** |
| ⚠️ Operational Risk Probability | **{result["operational_risk_probability"]}** |
| 🔧 Equipment Risk Probability | **{result["equipment_risk_probability"]}** |
| 🧠 Final Risk Score | **{result["final_risk_score"]}** |
| 🚦 Overall Risk Level | **{risk_level}** |

---

## ✅ Recommended Actions

{recommendations}

---

## 📚 RAG-lite Support Guidance

{guidance}

---

## 🔍 Explainability Notes

{explanations}
"""

def run_control_tower_ui(
    workflow_complexity,
    num_cases,
    department_congestion,
    queue_intensity,
    external_disruption,
    equipment_usage_level,
    days_since_maintenance,
    staff_experience,
    current_resource_utilization,
):
    result = run_control_tower_system(
        workflow_complexity,
        num_cases,
        department_congestion,
        queue_intensity,
        external_disruption,
        equipment_usage_level,
        days_since_maintenance,
        staff_experience,
        current_resource_utilization,
    )

    pretty_report = format_control_tower_report(result)
    return pretty_report, result

# =========================
# 6C. Batch CSV Prediction
# =========================
def run_batch_prediction(csv_file):
    if csv_file is None:
        return pd.DataFrame({"error": ["Please upload a CSV file."]})

    batch_df = pd.read_csv(csv_file.name)

    required_columns = [
        "workflow_complexity",
        "num_cases",
        "department_congestion",
        "queue_intensity",
        "external_disruption",
        "equipment_usage_level",
        "days_since_maintenance",
        "staff_experience",
        "current_resource_utilization",
    ]

    missing_columns = [
        col for col in required_columns
        if col not in batch_df.columns
    ]

    if missing_columns:
        return pd.DataFrame({
            "error": [f"Missing required columns: {missing_columns}"]
        })

    output_rows = []

    for _, row in batch_df.iterrows():
        result = run_control_tower_system(
            workflow_complexity=row["workflow_complexity"],
            num_cases=row["num_cases"],
            department_congestion=row["department_congestion"],
            queue_intensity=row["queue_intensity"],
            external_disruption=row["external_disruption"],
            equipment_usage_level=row["equipment_usage_level"],
            days_since_maintenance=row["days_since_maintenance"],
            staff_experience=row["staff_experience"],
            current_resource_utilization=row["current_resource_utilization"],
        )

        risk_level = get_risk_level(result["final_risk_score"])

        output_rows.append({
            "scenario_id": row.get("scenario_id", ""),
            "staff_id": row.get("staff_id", ""),
            "equipment_id": row.get("equipment_id", ""),
            "department": row.get("department", ""),
            "planned_start_hour": row.get("planned_start_hour", ""),
            "predicted_workload": result["predicted_workload"],
            "operational_risk_probability": result["operational_risk_probability"],
            "equipment_risk_probability": result["equipment_risk_probability"],
            "final_risk_score": result["final_risk_score"],
            "risk_level": risk_level,
            "top_recommendation": result["recommendations"][0],
            "explanation_summary": result["explanations"][0],
        })

    return pd.DataFrame(output_rows)

# =========================
# 7. Simulated Trust Record
# =========================
def create_trust_record(record_id, staff_id, department, record_status):
    proof_data = {
        "record_id": record_id,
        "staff_id": staff_id,
        "department": department,
        "record_status": record_status,
        "timestamp_utc": datetime.utcnow().isoformat(),
    }

    proof_string = str(proof_data)
    proof_hash = hashlib.sha256(proof_string.encode()).hexdigest()

    return {
        "record_data": proof_data,
        "record_hash": proof_hash,
        "trust_layer_status": "Simulated only - not yet written to blockchain or immutable audit store",
    }

def view_decision_logs():
    return decision_logs

def clear_decision_logs():
    decision_logs.clear()
    return {"status": "Decision logs cleared."}

# =========================
# 8. Gradio App
# =========================
with gr.Blocks(title="AI Operational Control Tower") as demo:
    gr.Markdown(
        """
        # 🧠 AI Operational Control Tower

        **A multi-agent AI prototype for predictive, explainable, and coordinated operational decision-making.**

        This healthcare-facing demo illustrates how a modular AI control system can support:

        - 📊 Workload forecasting
        - ⚠️ Operational risk prediction
        - 🔧 Equipment reliability monitoring
        - 📚 RAG-lite support guidance
        - 🔍 Explainability
        - 🧠 Coordinated recommendations
        - 📂 Batch scenario prediction
        - 🔐 Simulated trust / audit record
        """
    )

    with gr.Tab("🧠 Control Tower Simulation"):
        gr.Markdown(
            """
            This demo uses healthcare-style operational features to 
            simulate workload, risk, equipment reliability, and resource utilization.
            """
        )

        with gr.Row():
            with gr.Column():
                workflow_complexity = gr.Number(
                    label="Workflow Complexity / Process Effort",
                    value=12,
                )
                num_cases = gr.Number(
                    label="Number of Cases / Appointments",
                    value=20,
                )
                department_congestion = gr.Slider(
                    0,
                    1,
                    value=0.65,
                    label="Department Congestion Score",
                )
                queue_intensity = gr.Slider(
                    0,
                    1,
                    value=0.55,
                    label="System Load / Queue Intensity",
                )
                external_disruption = gr.Radio(
                    [0, 1],
                    value=0,
                    label="External Disruption Flag? 0 = No, 1 = Yes",
                )

            with gr.Column():
                equipment_usage_level = gr.Number(
                    label="Equipment Usage (Accumulated Hours)",
                    value=145000,
                )
                days_since_maintenance = gr.Number(
                    label="Days Since Last Equipment Maintenance",
                    value=90,
                )
                staff_experience = gr.Number(
                    label="Staff Experience (years)",
                    value=4,
                )
                current_resource_utilization = gr.Slider(
                    0,
                    100,
                    value=70,
                    label="Current Resource Utilization (%)",
                )

        predict_button = gr.Button("🚀 Run Operational Control Tower")

        pretty_output = gr.Markdown(label="Control Tower Report")
        raw_output = gr.JSON(label="Raw Agent Output")

        predict_button.click(
            fn=run_control_tower_ui,
            inputs=[
                workflow_complexity,
                num_cases,
                department_congestion,
                queue_intensity,
                external_disruption,
                equipment_usage_level,
                days_since_maintenance,
                staff_experience,
                current_resource_utilization,
            ],
            outputs=[pretty_output, raw_output],
        )

    with gr.Tab("📂 Batch Scenario Prediction"):
        gr.Markdown(
            """
            ### 📂 Batch Scenario Prediction

            Upload a planning CSV where each row represents one operational scenario,
            department workflow, or resource assignment.

            The Control Tower evaluates each row and returns a risk table for planning.
            """
        )

        csv_upload = gr.File(
            label="Upload planning CSV",
            file_types=[".csv"],
        )

        batch_button = gr.Button("📊 Run Batch Prediction")

        batch_output = gr.Dataframe(
            label="Batch Control Tower Output",
            interactive=False,
            wrap=True,
        )

        batch_button.click(
            fn=run_batch_prediction,
            inputs=[csv_upload],
            outputs=[batch_output],
        )

    with gr.Tab("🔐 Simulated Trust Record"):
        record_id = gr.Textbox(label="Record ID", value="REC001")
        staff_id = gr.Textbox(label="Staff ID", value="S001")
        department = gr.Textbox(label="Department", value="Emergency")
        record_status = gr.Dropdown(
            ["Completed", "Pending Review", "Escalated", "Deferred"],
            value="Completed",
            label="Record Status",
        )

        proof_button = gr.Button("Generate Trust Record Hash")
        proof_output = gr.JSON(label="Simulated Trust Record")

        proof_button.click(
            fn=create_trust_record,
            inputs=[record_id, staff_id, department, record_status],
            outputs=proof_output,
        )

    with gr.Tab("📜 Decision Logs"):
        view_logs_button = gr.Button("View Decision Logs")
        clear_logs_button = gr.Button("Clear Decision Logs")
        logs_output = gr.JSON(label="Decision Logs")

        view_logs_button.click(
            fn=view_decision_logs,
            inputs=[],
            outputs=logs_output,
        )

        clear_logs_button.click(
            fn=clear_decision_logs,
            inputs=[],
            outputs=logs_output,
        )

# =========================
# 9. Launch
# =========================
if __name__ == "__main__":
    demo.launch()
