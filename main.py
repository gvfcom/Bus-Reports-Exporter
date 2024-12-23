import json
import pandas as pd
from datetime import timedelta


# Load JSON data from a given file path
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


# Convert time in <day offset>.<hours>:<minutes> format to timedelta
def convert_time(day_offset_time):
    try:
        day_offset, time_str = day_offset_time.split('.')
        hours, minutes = map(int, time_str.split(':'))
        return timedelta(days=int(day_offset), hours=hours, minutes=minutes)
    except Exception as e:
        print(f"Error converting time: {e}")
        return timedelta(0)


# Convert timedelta to time in HH:MM format
def timedelta_to_time(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}"


# Step 1: Generate Duty Start and End Time Report
def generate_duty_times_report(duties, vehicles):
    report = []
    
    # Loop through each duty in the duties list
    for duty in duties:
        duty_id = duty['duty_id']
        
        # Find all vehicle events that match the current duty_id
        matching_events = [
            event for vehicle in vehicles 
            for event in vehicle['vehicle_events'] if event['duty_id'] == duty_id
        ]
        
        if matching_events:
            # Sort events by sequence to determine the correct start and end events
            sorted_events = sorted(matching_events, key=lambda ev: int(ev['vehicle_event_sequence']))
            start_event = sorted_events[0]
            end_event = sorted_events[-1]
            
            # Convert start and end times to timedelta objects
            start_time = convert_time(start_event.get('start_time', '0.00:00'))  # Default to '0.00:00' if missing
            end_time = convert_time(end_event.get('end_time', '0.00:00'))  # Default to '0.00:00' if missing
            
            # Append the duty information to the report list
            report.append({
                'Duty ID': duty_id,
                'Start time': timedelta_to_time(start_time),
                'End time': timedelta_to_time(end_time)
            })
    
    # Convert the report list into a DataFrame
    report_df = pd.DataFrame(report)
    
    return report_df


# Step 2: Add Start and End Stop Names to the Report
def add_stop_names_to_report(report, vehicles, stops):
    stop_map = {stop['stop_id']: stop['stop_name'] for stop in stops}
    
    # Ensure 'Duty ID' exists in report DataFrame before proceeding
    if 'Duty ID' not in report.columns:
        return report  # Skip if 'Duty ID' is missing
    
    # Iterate through each row in the report DataFrame
    for index, row in report.iterrows():
        duty_id = row['Duty ID']
        
        # Find the duty events that match the duty_id
        duty_events = [
            event for vehicle in vehicles 
            for event in vehicle['vehicle_events'] if event['duty_id'] == duty_id
        ]
        
        if duty_events:
            # Get the first and last event to determine the start and end stops
            start_event = duty_events[0]
            end_event = duty_events[-1]
            
            # Get the stop names using the stop_map
            start_stop = stop_map.get(start_event.get('origin_stop_id', 'Unknown'), 'Unknown')
            end_stop = stop_map.get(end_event.get('destination_stop_id', 'Unknown'), 'Unknown')
            
            # Add the stop names to the DataFrame
            report.loc[index, 'First service trip start stop'] = start_stop
            report.loc[index, 'Last service trip end stop'] = end_stop
    
    return report


# Step 3: Add Breaks Information to the Report
def add_breaks_to_report(report, vehicles, stops):
    stop_map = {stop['stop_id']: stop['stop_name'] for stop in stops}
    breaks_data = []
    
    # Ensure 'Duty ID' exists in report DataFrame before proceeding
    if 'Duty ID' not in report.columns:
        return report  # Skip if 'Duty ID' is missing
    
    # Iterate through each row in the report DataFrame
    for row in report.itertuples():
        duty_id = row._1  # Access Duty ID from the tuple
        
        # Find the duty events that match the duty_id
        duty_events = [
            event for vehicle in vehicles 
            for event in vehicle['vehicle_events'] if event['duty_id'] == duty_id
        ]
        
        # Loop through the events to find breaks between consecutive events
        for i in range(len(duty_events) - 1):
            start_event = duty_events[i]
            end_event = duty_events[i + 1]
            
            # Check if the events are a break and break end
            if start_event.get('vehicle_event_type') == 'Break' and end_event.get('vehicle_event_type') == 'Break End':
                break_duration = (convert_time(end_event['start_time']) - convert_time(start_event['end_time'])).total_seconds() / 60
                
                # Only add breaks longer than 15 minutes
                if break_duration > 15:
                    breaks_data.append({
                        'Duty ID': duty_id,  # Ensure 'Duty ID' is added here
                        'Break duration (minutes)': break_duration,
                        'Break start time': timedelta_to_time(convert_time(start_event['start_time'])),
                        'Break stop name': stop_map.get(start_event.get('origin_stop_id', 'Unknown'), 'Unknown')
                    })

    # Create a DataFrame from the breaks data
    breaks_df = pd.DataFrame(breaks_data)

    # Add default empty columns to the breaks_df if no breaks data exists
    if breaks_df.empty:
        breaks_df[['Duty ID', 'Break duration (minutes)', 'Break start time', 'Break stop name']] = pd.NA
        
    # Merge the breaks data with the main report DataFrame
    merged_df = pd.merge(report, breaks_df, on='Duty ID', how='left')
    
    return merged_df


# Main Execution Block
if __name__ == "__main__":
    # Load the JSON dataset
    data = load_json('mini_json_dataset.json')
    
    # Extract relevant sections from the JSON data
    stops = data['stops']
    vehicles = data['vehicles']
    duties = data['duties']
    
    # Step 1: Generate the Duty Times Report
    duty_times_report = generate_duty_times_report(duties, vehicles)
    if duty_times_report is not None:
        duty_times_report.to_csv('duty_times_report.csv', index=False)
    
    # Step 2: Add Start and End Stop Names to the Report
    if duty_times_report is not None:
        start_end_names_report = add_stop_names_to_report(duty_times_report, vehicles, stops)
        if start_end_names_report is not None:
            start_end_names_report.to_csv('start_end_names_report.csv', index=False)
    
    # Step 3: Add Breaks Information to the Report
    if start_end_names_report is not None:
        break_report = add_breaks_to_report(start_end_names_report, vehicles, stops)
        if break_report is not None:
            break_report.to_csv('break_report.csv', index=False)
    
    # Final Report: Save to CSV with all the relevant columns
    if break_report is not None:
        final_report = break_report[['Duty ID', 'Start time', 'End time', 
                                     'First service trip start stop', 'Last service trip end stop',
                                     'Break duration (minutes)', 'Break start time', 'Break stop name']]
        final_report.to_csv('duty_report.csv', index=False)

        print("\nReport generated and saved as 'duty_report.csv'")