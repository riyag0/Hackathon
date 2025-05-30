import requests

payload = {
    "prediction_id": "pred_1",
    "label": "TP",
    "reviewer_id": "test_user"
}
response = requests.post("http://localhost:5000/feedback", json=payload)
print(response.json())
