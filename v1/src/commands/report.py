from services.html_service import generate_dashboard


def run():

    file = generate_dashboard()

    print(
        f"Dashboard generated: {file}"
    )