import pandas as pd
import json
from datetime import datetime, timedelta
import numpy as np

# Create dummy data for predictions
n = 10
now = datetime.utcnow()
predictions = []
for i in range(n):
    predictions.append({
        'prediction_id': f'pred_{i+1}',
        'patient_id': f'patient_{np.random.randint(1000, 2000)}',
        'flag_type': np.random.choice(['High BP', 'Low HR', 'Arrhythmia']),
        'risk_score': round(np.random.uniform(0.1, 0.99), 2),
        'flag_time': (now - timedelta(hours=np.random.randint(1, 72))).isoformat(),
        'summary_features': json.dumps({
            'age': int(np.random.randint(40, 90)),
            'systolic_bp': int(np.random.randint(90, 180)),
            'diastolic_bp': int(np.random.randint(60, 110)),
            'heart_rate': int(np.random.randint(50, 120)),
            'recent_event': np.random.choice(['None', 'Fall', 'Hospitalization'])
        })
    })

df = pd.DataFrame(predictions)
df.to_parquet('create_dummy_predictions.parquet', index=False)
print('Dummy predictions parquet file created.')
