import json

CODES_FILE = "codes.json"

def load_codes():
    try:
        with open(CODES_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"codes": []}

def save_codes(data):
    with open(CODES_FILE, "w") as file:
        json.dump(data, file, indent=4)

def jload(amount):
    data = load_codes()
    print(f"Upload codes for {amount} UC:")
    
    codes_input = []
    while True:
        code = input("Enter code (or type 'done' to finish): ")
        if code.lower() == 'done':
            break
        codes_input.append({"code": code, "redeemed": False})
    
    if not codes_input:
        print("No codes provided.")
        return
    
    for entry in data["codes"]:
        if entry["amount"] == amount:
            entry["codes"].extend(codes_input)
            break
    else:
        data["codes"].append({"amount": amount, "codes": codes_input, "price": float(amount)})
    
    save_codes(data)
    print(f"Added {len(codes_input)} codes for amount: {amount}")

if __name__ == "__main__":
    while True:
        command = input("Enter command: ")
        parts = command.split()
        if len(parts) == 2 and parts[0].lower() == "jload" and parts[1].isdigit():
            jload(int(parts[1]))
        elif command.lower() == "exit":
            break
        else:
            print("Invalid command. Use 'Jload <amount>' or 'exit' to quit.")
