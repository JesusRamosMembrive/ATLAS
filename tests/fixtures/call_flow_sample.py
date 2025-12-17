"""Sample file for testing Call Flow extraction."""


def helper_function():
    """A helper function that does something."""
    return "helper result"


def process_data(data):
    """Process data using helper."""
    result = helper_function()
    return f"processed: {data} with {result}"


def load_content():
    """Load content from somewhere."""
    return {"key": "value"}


class DataHandler:
    """Handler class for data operations."""

    def __init__(self):
        self.data = None

    def load(self):
        """Load data using load_content."""
        self.data = load_content()
        return self.data

    def process(self):
        """Process the loaded data."""
        if self.data:
            return process_data(self.data)
        return None

    def handle(self):
        """Handle the full workflow."""
        self.load()
        result = self.process()
        return result


def on_button_click():
    """Event handler simulating a button click."""
    handler = DataHandler()
    result = handler.handle()
    print(result)
    return result


def main():
    """Main entry point."""
    on_button_click()


if __name__ == "__main__":
    main()
