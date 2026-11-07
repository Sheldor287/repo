import secrets

# Generate a secure random hex key (e.g., 32 bytes / 64 hex characters)
api_key = secrets.token_hex(32)
print(api_key)

# Generate a URL-safe base64 string
url_token = secrets.token_urlsafe(32)
print(url_token)
