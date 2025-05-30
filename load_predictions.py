import pandas as pd
import os

# Load the Parquet file
predictions_df = pd.read_parquet('create_dummy_predictions.parquet')

# Ensure required columns are present
required_columns = [
    'prediction_id',
    'patient_id',
    'flag_type',
    'risk_score',
    'flag_time',
    'summary_features'
]

missing_columns = [col for col in required_columns if col not in predictions_df.columns]
if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")

print("All required columns are present.")

# Display the first few rows
print(predictions_df.head())

# Load and display feedback.parquet as a table
if os.path.exists('create_dummy_feedback.parquet'):
    feedback_df = pd.read_parquet('create_dummy_feedback.parquet')
    # Merge with predictions to get patient_id and flag_type
    merged = feedback_df.merge(predictions_df[['prediction_id', 'patient_id', 'flag_type']], on='prediction_id', how='left')
    display_cols = [
        'prediction_id',
        'patient_id',
        'flag_type',
        'label',
        'review_time',
        'reviewer_id',
        'notes'
    ]
    print("\nFeedback Table:")
    print(merged[display_cols].to_string(index=False))
else:
    print("\nNo create_dummy_feedback.parquet file found.")


