"""
Operaciones Basicas - Las cuatro operaciones matematicas fundamentales
"""


def suma(a: float, b: float) -> float:
    """Suma dos numeros."""
    return a + b


def resta(a: float, b: float) -> float:
    """Resta el segundo numero del primero."""
    return a - b


def multiplicacion(a: float, b: float) -> float:
    """Multiplica dos numeros."""
    return a * b


def division(a: float, b: float) -> float:
    """Divide el primer numero entre el segundo.

    Raises:
        ValueError: Si el divisor es cero.
    """
    if b == 0:
        raise ValueError("No se puede dividir entre cero")
    return a / b


if __name__ == "__main__":
    # Ejemplos de uso
    print(f"Suma: 10 + 5 = {suma(10, 5)}")
    print(f"Resta: 10 - 5 = {resta(10, 5)}")
    print(f"Multiplicacion: 10 * 5 = {multiplicacion(10, 5)}")
    print(f"Division: 10 / 5 = {division(10, 5)}")
