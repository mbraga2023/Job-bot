# Job Bot v2

This is the v2 branch of the Job Bot project, featuring a modernized architecture and improved workflows for job intelligence automation.

## Key improvements

- **Modular design**: Separated concerns into clear service layers
- **Type safety**: Enhanced type hints and validation
- **Database schema**: Optimized for performance with foreign keys
- **CLI enhancements**: Better command structure and error handling
- **AI integration**: Ollama-based job classification pipeline

## Structure

```
v2/
├── config.py
├── core/
│   ├── browser.py
│   ├── database.py
│   ├── date_utils.py
│   ├── keywords.py
│   ├── seniority.py
│   └── ...
├── dashboard/
│   └── server.py
├── flows/
│   ├── careers/
│   │   ├── adapters/
│   │   └── ...
│   └── telegram/
│       └── analyzers/
├── tests/
└── ...
```

## How to use

This branch contains the updated codebase for the Job Bot project. To use it:

1. Ensure you have Python 3.10+ installed
2. Install dependencies with `pip install -r requirements.txt`
3. Configure your environment with `.env` file
4. Run the dashboard with `python src/main.py dashboard`

## Notes

- This branch is a development version with ongoing improvements
- The full project documentation is available in the root `README.md`
- The v2 branch focuses on long-term maintainability and scalability
