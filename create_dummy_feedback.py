import pandas as pd
import datetime
from datetime import timedelta
import numpy as np

# Create dummy feedback for a few predictions
feedback = []
for i in range(3):
    feedback.append({
        'prediction_id': f'pred_{i+1}',
        'label': np.random.choice(['TP', 'FP']),
        'review_time': (datetime.datetime.utcnow() - timedelta(hours=np.random.randint(1, 48))).isoformat(),
        'reviewer_id': f'clinician_{np.random.randint(1,4)}',
        'notes': np.random.choice(['', 'Reviewed, looks good.', 'Needs follow-up.'])
    })

feedback_df = pd.DataFrame(feedback)
feedback_df.to_parquet('create_dummy_feedback.parquet', index=False)
print('Dummy feedback parquet file created.')
