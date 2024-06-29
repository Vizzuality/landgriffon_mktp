# Landgriffon Marketplace

This repository contains the Landgriffon Marketplace Subscriptions Manager built with FastAPI.

## Table of Contents

- [Project Structure](#project-structure)
- [Setup](#setup)
  - [Backend Setup](#backend-setup)
- [Running the Application](#running-the-application)
  - [Using Docker Compose](#using-docker-compose)
  - [Running Backend Separately](#running-backend-separately)
  - [Running Frontend Separately](#running-frontend-separately)
- [Environment Variables](#environment-variables)
- [Contributing](#contributing)
- [License](#license)

## Project Structure

<pre>
landgriffon_mktp/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── pubsub.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── subscriptions.py
│   ├── main.py
│   ├── .env
│   ├── .gitignore
│   ├── requirements.txt
│   ├── logging_config.py
├── .gitignore
├── README.md
</pre>

## Setup

### Backend Setup

1. **Navigate to the backend directory**:

   ```bash
   cd backend
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv env
   source env/bin/activate  # On Windows use `env\Scripts\activate`
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the `backend` directory and add the required environment variables:
   ```plaintext
   GOOGLE_CLOUD_PROJECT=your_project_id
   PUBSUB_SUBSCRIPTION=your_subscription_acount
   ACCOUNTS_DATABASE=your_db_connection
   GOOGLE_APPLICATION_CREDENTIALS=your_google_credentials
   ```

## Running the Application

### Using Docker Compose

1. **Ensure you are in the root directory** of the project (`landgriffon_mktp`):

   ```bash
   cd /path/to/landgriffon_mktp
   ```

2. **Create a .env file** in the root directory with the following content:

   ```plaintext
   GOOGLE_CLOUD_PROJECT=your_project_id
   PUBSUB_SUBSCRIPTION=codelab
   ACCOUNTS_DATABASE=sqlite:///./test.db
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json
   ```

3. **Build and run the containers**:
   ```bash
   docker-compose up --build
   ```

### Running Backend Separately

1. **Navigate to the backend directory**:

   ```bash
   cd backend
   ```

2. **Activate the virtual environment**:

   ```bash
   source env/bin/activate  # On Windows use `env\Scripts\activate`
   ```

3. **Run the backend server**:
   ```bash
   uvicorn app.main:app --reload
   ```

## Environment Variables

### Backend

- `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID
- `PUBSUB_SUBSCRIPTION`: The Pub/Sub subscription name
- `ACCOUNTS_DATABASE`: The database connection string
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud credentials JSON file

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the terms of the MIT License.
