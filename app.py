import streamlit as st
import requests
import json
import openai
import os
from datetime import datetime, timedelta

# Configuration and Environment Variables
def get_env_variable(var_name):
    """Safely get environment variable or show error in Streamlit."""
    value = os.getenv(var_name)
    if not value:
        st.error(f"Missing {var_name} environment variable. Please set it in Streamlit Cloud.")
        st.stop()
    return value

# Initialize configuration
def init_config():
    st.set_page_config(
        page_title="DU Status Checker",
        page_icon="🔍",
        layout="wide"
    )

    # Get environment variables
    return {
        'OPENAI_API_KEY': get_env_variable('OPENAI_API_KEY'),
        'BASE_URL': get_env_variable('BASE_URL'),
        'DEFAULT_POINTS': int(os.getenv('DEFAULT_POINTS', '24'))
    }

# Calculate default time range
def get_time_range():
    now = datetime.now()
    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(days=1)).timestamp() * 1000)
    return str(start_time), str(end_time)

# Main application code
def main():
    # Initialize configuration
    config = init_config()
    
    # Set up OpenAI
    openai.api_key = config['OPENAI_API_KEY']
    
    # Calculate time range
    default_start_time, default_end_time = get_time_range()
    
    # Base URLs for endpoints
    base_url = config['BASE_URL']
    du_name_endpoint = f"{base_url}/duId"
    du_status_endpoint = f"{base_url}/duId/batch/withBandwidth"

    # Streamlit UI
    st.title("DU Status Identification")
    st.write("Enter Deployment Unit (DU) IDs manually to fetch their status and associated names.")

    # Input field for DU IDs
    du_input = st.text_area("Enter DU IDs (comma-separated)", placeholder="e.g., 1639, 2092")

    def fetch_du_name(du_id):
        try:
            response = requests.get(f"{du_name_endpoint}/{du_id}/name", timeout=10)
            response.raise_for_status()
            return response.json().get("name", "Unknown DU Name")
        except requests.exceptions.RequestException as e:
            st.warning(f"Network error fetching DU name: {e}")
            return "Unknown DU Name"
        except Exception as e:
            st.error(f"Error fetching DU name: {e}")
            return "Error fetching name"

    def fetch_du_status(du_ids):
        results = {}
        for du_id in du_ids:
            payload = json.dumps([du_id])
            params = {
                'start': default_start_time,
                'end': default_end_time,
                'points': config['DEFAULT_POINTS']
            }
            headers = {'Content-Type': 'application/json'}
            try:
                response = requests.get(
                    du_status_endpoint,
                    headers=headers,
                    params=params,
                    data=payload,
                    timeout=10
                )
                response.raise_for_status()
                results[du_id] = response.json()
            except requests.exceptions.RequestException as e:
                st.warning(f"Network error for DU {du_id}: {e}")
                results[du_id] = f"Network Error: {str(e)}"
            except Exception as e:
                st.error(f"Error processing DU {du_id}: {e}")
                results[du_id] = f"Processing Error: {str(e)}"
        return results

    def analyze_with_gpt(data):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an assistant analyzing DU status data."},
                    {"role": "user", "content": f"""
                    Analyze the following DU status data and provide detailed bullet points for:
                    1. Each ID and its components (e.g., BIFLOW, FIREWALL, etc.).
                    2. For each component, specify its status (active, inactive, no data, etc.).
                    3. Make it clear, crisp, and well-structured.

                    Data:
                    {json.dumps(data, indent=2)}
                    """}
                ],
                temperature=0.1
            )
            return response['choices'][0]['message']['content']
        except openai.error.OpenAIError as e:
            st.error(f"OpenAI API error: {e}")
            return "Error analyzing data with GPT"
        except Exception as e:
            st.error(f"Unexpected error during analysis: {e}")
            return "Error processing analysis"

    # Button to trigger the process
    if st.button("Check DU Status"):
        if not du_input.strip():
            st.error("Please enter at least one DU ID.")
        else:
            with st.spinner("Fetching DU status and names..."):
                # Convert DU IDs from input to a list
                du_ids = [du.strip() for du in du_input.split(",") if du.strip()]
                
                # Fetch DU statuses
                statuses = fetch_du_status(du_ids)

                # Display results
                st.subheader("DU Status Results")
                collected_data = {}
                
                for du_id, status in statuses.items():
                    du_name = fetch_du_name(du_id)
                    st.write(f"**DU ID**: {du_id} - **Name**: {du_name}")
                    
                    if isinstance(status, dict):
                        st.json(status)
                        collected_data[du_id] = {"name": du_name, "status": status}
                    else:
                        st.error(f"Error for DU ID {du_id}: {status}")

                # Analyze results with GPT
                if collected_data:
                    st.subheader("LLM Detailed Analysis")
                    with st.spinner("Analyzing data with GPT..."):
                        explanation = analyze_with_gpt(collected_data)
                        st.write("**Analysis**:")
                        st.markdown(explanation)

if __name__ == "__main__":
    main()
