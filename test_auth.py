# import os
# from dotenv import load_dotenv

# # This line loads local variables if you ever run this outside of Codespaces
# load_dotenv() 

# def verify_api_key():
#     print("[SYSTEM] Checking Environment Variables for API Key...")
    
#     # os.getenv safely checks for the variable. Returns None if not found.
#     api_key = os.getenv("ANTHROPIC_API_KEY")
    
#     if api_key is None:
#         print("❌ ERROR: ANTHROPIC_API_KEY is missing!")
#         print("   Did you add it to GitHub Secrets and Rebuild the Container?")
#         return

#     # Basic validation: Check length and prefix without printing the key
#     if api_key.startswith("sk-ant-") and len(api_key) > 80:
#         print("✅ SUCCESS: API Key detected and formatted correctly.")
#         print("   Your Python environment is authorized to contact Claude 3.5.")
#     else:
#         print("⚠️ WARNING: Key found, but format looks incorrect (should start with 'sk-ant-').")

# if __name__ == "__main__":
#     verify_api_key()