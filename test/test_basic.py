import os

def test_main_file_exists():
    # Check if the main application entry point exists
    main_file_path = "src/infra_generator/main.py"
    assert os.path.exists(main_file_path), f"Expected file not found: {main_file_path}"
