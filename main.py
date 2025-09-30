# mainはモックなので触らないこと


def main():
    # NOTE: 本番環境では起動時にDB初期化が必要
    # from infra.storage.rds import initialize_database
    # initialize_database()

    print("Hi")


if __name__ == "__main__":
    main()
