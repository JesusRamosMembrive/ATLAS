def print_is_even(number: int) -> None:
    """
    Print if a number is even.
    :return: None
    :rtype: None
    """
    print(f"{number} is even.")

def print_is_odd(number: int) -> None:
    """
    Print if a number is odd.
    :return: None
    :rtype: None
    """
    print(f"{number} is odd.")


def print_is_zero() -> None:
    """
    Print if a number is zero.
    :return: None
    :rtype: None
    """
    print("Number is zero.")

def even_or_odd(numbers: list) -> dict:
    """
    Determines if a number is even or odd, add a list and return.
    :param number: Description
    :return: Description
    :rtype: list
    """
    dict_of_results = {}
    for number in numbers:
        if number == 0:
            dict_of_results[number] = "zero"
            print_is_zero()
        elif number % 2 == 0:
            dict_of_results[number] = "even"
            print_is_even(number)
        else:
            dict_of_results[number] = "odd"
            print_is_odd(number)
    return dict_of_results

if __name__ == "__main__":

    sample_numbers = [0, 1, 2, 3, 4, 5, 6]
    results = even_or_odd(sample_numbers)
    print(results)
