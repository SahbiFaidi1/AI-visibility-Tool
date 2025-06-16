from mistralai.client import MistralClient

def test_api_key():
    try:
        api_key = "LyOZOnyciBFsEiMlgxFSgmDPohaYZ5yq"
        client = MistralClient(api_key=api_key)
        
        # Make a simple test call
        response = client.chat(
            model="mistral-tiny",
            messages=[{"role": "user", "content": "Hello"}]
        )
        print("API key is valid!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", str(e))
        print("The API key appears to be invalid or expired.")

if __name__ == "__main__":
    test_api_key() 