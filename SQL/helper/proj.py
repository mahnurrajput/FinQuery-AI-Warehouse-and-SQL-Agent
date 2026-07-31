import json, csv
with open('mcc_codes.json') as f:
    data = json.load(f)
with open('mcc_codes.csv','w',newline='') as out:
    writer = csv.writer(out)
    writer.writerow(['mcc_code','description'])
    for k,v in data.items():
        writer.writerow([k,v])

with open("train_fraud_labels.json", "r") as f:
    data = json.load(f)

# Step 2: Access the nested "target" dictionary
target_data = data.get("target", {})

# Step 3: Write to CSV
with open("fraud_labels.csv", "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["transaction_id", "fraud_label"])  # header

    # Loop through nested dictionary
    for transaction_id, label in target_data.items():
        writer.writerow([transaction_id, label])
