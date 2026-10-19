from src.auth import get_credentials

def main():
    creds = get_credentials()
    print("Autenticación finalizada. Credenciales válidas: ", creds)

if __name__ == "__main__":
    main()