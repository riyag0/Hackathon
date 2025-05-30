from flask import Flask, request, jsonify, render_template_string
import pandas as pd
import os
from datetime import datetime
import json

app = Flask(__name__)

PREDICTIONS_PATH = 'create_dummy_predictions.parquet'
FEEDBACK_PATH = 'create_dummy_feedback.parquet'

@app.route('/flags', methods=['GET'])
def get_unreviewed_flags():
    #
    predictions_df = pd.read_parquet(PREDICTIONS_PATH)

    
    if os.path.exists(FEEDBACK_PATH):
        feedback_df = pd.read_parquet(FEEDBACK_PATH)
        reviewed_ids = set(feedback_df['prediction_id'])
    else:
        reviewed_ids = set()

   
    unreviewed_df = predictions_df[~predictions_df['prediction_id'].isin(reviewed_ids)]
    if unreviewed_df.empty:
        return jsonify([])
    limit = request.args.get('limit', default=None, type=int)
    sort_by = request.args.get('sort_by', default=None, type=str)

    if sort_by:
       
        parts = sort_by.split()
        col = parts[0]
        ascending = not (len(parts) > 1 and parts[1].lower().startswith('desc'))
        if col in unreviewed_df.columns:
            unreviewed_df = unreviewed_df.sort_values(by=col, ascending=ascending)

    if limit:
        unreviewed_df = unreviewed_df.head(limit)

    
    def safe_json(val):
        if isinstance(val, str):
            try:
                import json
                return json.loads(val)
            except Exception:
                return val
        return val

    result = unreviewed_df.copy()
    result['summary_features'] = result['summary_features'].apply(safe_json)

    
    output = result[
        [
            'prediction_id',
            'patient_id',
            'flag_type',
            'risk_score',
            'flag_time',
            'summary_features'
        ]
    ].to_dict(orient='records')

    return jsonify(output)

@app.route('/feedback', methods=['POST'])
def post_feedback():
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({'error': f'Invalid JSON: {e}'}), 400

    required_fields = ['prediction_id', 'label', 'reviewer_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    if data['label'] not in ['TP', 'FP']:
        return jsonify({'error': 'label must be "TP" or "FP"'}), 400

    # Check that prediction_id exists
    try:
        predictions_df = pd.read_parquet(PREDICTIONS_PATH)
        if data['prediction_id'] not in predictions_df['prediction_id'].values:
            return jsonify({'error': 'prediction_id not found in predictions'}), 400
    except Exception as e:
        return jsonify({'error': f'Could not read predictions file: {e}'}), 500

    feedback_record = {
        'prediction_id': data['prediction_id'],
        'label': data['label'],
        'notes': data.get('notes', ''),
        'reviewer_id': data['reviewer_id'],
        'review_time': datetime.utcnow().isoformat()
    }

    try:
        if os.path.exists(FEEDBACK_PATH):
            feedback_df = pd.read_parquet(FEEDBACK_PATH)
            feedback_df = pd.concat([feedback_df, pd.DataFrame([feedback_record])], ignore_index=True)
        else:
            feedback_df = pd.DataFrame([feedback_record])
        feedback_df.to_parquet(FEEDBACK_PATH, index=False)
    except Exception as e:
        return jsonify({'error': f'Could not save feedback: {e}'}), 500

    return jsonify({'status': 'success'}), 201

@app.route('/')
def index():
    
    predictions_df = pd.read_parquet(PREDICTIONS_PATH)
    
    if os.path.exists(FEEDBACK_PATH):
        feedback_df = pd.read_parquet(FEEDBACK_PATH)
        reviewed_ids = set(feedback_df['prediction_id'])
    else:
        reviewed_ids = set()
    
    unreviewed_df = predictions_df[~predictions_df['prediction_id'].isin(reviewed_ids)]
    
    rows = unreviewed_df[['prediction_id', 'patient_id', 'flag_type', 'risk_score', 'flag_time']].to_dict(orient='records')
   
    html = '''
    <html>
    <head>
        <title>Unreviewed Predictions</title>
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            th { background-color: #f2f2f2; }
            button { padding: 5px 10px; }
        </style>
    </head>
    <body>
        <h2>Unreviewed Predictions</h2>
        <table>
            <tr>
                <th>Patient ID</th>
                <th>Flag Type</th>
                <th>Risk Score</th>
                <th>Flag Time</th>
                <th>Action</th>
            </tr>
            {% for row in rows %}
            <tr>
                <td>{{ row['patient_id'] }}</td>
                <td>{{ row['flag_type'] }}</td>
                <td>{{ row['risk_score'] }}</td>
                <td>{{ row['flag_time'] }}</td>
                <td>
                    <form action="/review/{{ row['prediction_id'] }}" method="get">
                        <button type="submit">Review</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    '''
    return render_template_string(html, rows=rows)

@app.route('/review/<prediction_id>', methods=['GET', 'POST'])
def review_prediction(prediction_id):
    predictions_df = pd.read_parquet(PREDICTIONS_PATH)
    row = predictions_df[predictions_df['prediction_id'] == prediction_id]
    if row.empty:
        return f"Prediction with id {prediction_id} not found.", 404
    row = row.iloc[0]
    summary = row['summary_features']
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            pass
    message = None
    reviewed = False
    if request.method == 'POST':
        label = request.form.get('label')
        notes = request.form.get('notes', '')
        reviewer_id = request.form.get('reviewer_id', 'clinician')
        if label not in ['TP', 'FP']:
            message = 'Please select True Positive or False Positive.'
        else:
            # Submit feedback
            feedback_payload = {
                'prediction_id': prediction_id,
                'label': label,
                'notes': notes,
                'reviewer_id': reviewer_id
            }
            import requests
            try:
                r = requests.post(request.url_root.rstrip('/') + '/feedback', json=feedback_payload)
                if r.status_code == 201:
                    message = 'Feedback submitted successfully. This prediction is now marked as reviewed.'
                    reviewed = True
                else:
                    message = f'Error submitting feedback: {r.json().get("error", r.text)}'
            except Exception as e:
                message = f'Error submitting feedback: {e}'
    html = '''
    <html>
    <head>
        <title>Review Prediction</title>
        <style>
            table { border-collapse: collapse; width: 50%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            th { background-color: #f2f2f2; text-align: left; }
            .success { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h2>Review Prediction: {{ prediction_id }}</h2>
        <h3>Summary Features</h3>
        <table>
            <tr><th>Feature</th><th>Value</th></tr>
            {% for k, v in summary.items() %}
            <tr><td>{{ k }}</td><td>{{ v }}</td></tr>
            {% endfor %}
        </table>
        <br>
        {% if message %}
            <div class="{{ 'success' if reviewed else 'error' }}">{{ message }}</div>
        {% endif %}
        {% if not reviewed %}
        <form method="post">
            <label><b>Label:</b></label><br>
            <input type="radio" id="tp" name="label" value="TP">
            <label for="tp">True Positive</label><br>
            <input type="radio" id="fp" name="label" value="FP">
            <label for="fp">False Positive</label><br><br>
            <label for="notes"><b>Notes (optional):</b></label><br>
            <textarea id="notes" name="notes" rows="3" cols="40"></textarea><br><br>
            <input type="hidden" name="reviewer_id" value="clinician">
            <button type="submit">Submit Feedback</button>
        </form>
        {% endif %}
        <br>
        <a href="/">Back to list</a>
    </body>
    </html>
    '''
    return render_template_string(html, prediction_id=prediction_id, summary=summary, message=message, reviewed=reviewed)

@app.route('/metrics')
def metrics():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io
    import base64
    from datetime import datetime

    # Load data
    predictions_df = pd.read_parquet(PREDICTIONS_PATH)
    if os.path.exists(FEEDBACK_PATH):
        feedback_df = pd.read_parquet(FEEDBACK_PATH)
    else:
        feedback_df = pd.DataFrame(columns=['prediction_id', 'label', 'review_time', 'reviewer_id', 'notes'])

    # Merge for metrics
    merged = feedback_df.merge(predictions_df[['prediction_id', 'flag_type', 'flag_time']], on='prediction_id', how='left')

    # Metrics
    total_predictions = len(predictions_df)
    num_reviewed = len(feedback_df)
    tp_count = (feedback_df['label'] == 'TP').sum()
    fp_count = (feedback_df['label'] == 'FP').sum()

    # Review latency (in hours)
    if not merged.empty:
        merged['flag_time'] = pd.to_datetime(merged['flag_time'])
        merged['review_time'] = pd.to_datetime(merged['review_time'])
        merged['latency_hours'] = (merged['review_time'] - merged['flag_time']).dt.total_seconds() / 3600
        avg_latency = merged['latency_hours'].mean()
    else:
        avg_latency = None

    # Distribution of labels by flag_type
    if not merged.empty:
        dist = merged.groupby(['flag_type', 'label']).size().unstack(fill_value=0)
    else:
        dist = pd.DataFrame()

    # Bar chart for label counts
    fig1, ax1 = plt.subplots()
    ax1.bar(['True Positive', 'False Positive'], [tp_count, fp_count], color=['green', 'red'])
    ax1.set_ylabel('Count')
    ax1.set_title('Label Counts')
    buf1 = io.BytesIO()
    plt.tight_layout()
    fig1.savefig(buf1, format='png')
    plt.close(fig1)
    buf1.seek(0)
    img1 = base64.b64encode(buf1.getvalue()).decode()

    # Bar chart for distribution by flag_type
    if not dist.empty:
        fig2, ax2 = plt.subplots()
        dist.plot(kind='bar', ax=ax2)
        ax2.set_ylabel('Count')
        ax2.set_title('Label Distribution by Flag Type')
        plt.tight_layout()
        buf2 = io.BytesIO()
        fig2.savefig(buf2, format='png')
        plt.close(fig2)
        buf2.seek(0)
        img2 = base64.b64encode(buf2.getvalue()).decode()
    else:
        img2 = None

    html = '''
    <html>
    <head>
        <title>Review Metrics</title>
        <style>
            .counter {{ font-size: 2em; margin: 10px 0; }}
            .metrics {{ display: flex; gap: 40px; }}
            .chart {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h2>Review Metrics</h2>
        <div class="metrics">
            <div><div class="counter">{total_predictions}</div>Total Predictions</div>
            <div><div class="counter">{num_reviewed}</div>Reviewed</div>
            <div><div class="counter">{tp_count}</div>True Positives</div>
            <div><div class="counter">{fp_count}</div>False Positives</div>
            <div><div class="counter">{latency}</div>Avg. Review Latency (hrs)</div>
        </div>
        <div class="chart">
            <h3>Label Counts</h3>
            <img src="data:image/png;base64,{img1}"/>
        </div>
        <div class="chart">
            <h3>Label Distribution by Flag Type</h3>
            {img2_block}
        </div>
        <a href="/">Back to list</a>
    </body>
    </html>
    '''.format(
        total_predictions=total_predictions,
        num_reviewed=num_reviewed,
        tp_count=tp_count,
        fp_count=fp_count,
        latency=f"{avg_latency:.2f}" if avg_latency is not None else 'N/A',
        img1=img1,
        img2_block=f'<img src="data:image/png;base64,{img2}"/>' if img2 else '<i>No data</i>'
    )
    return html

if __name__ == '__main__':
    app.run(debug=True)
