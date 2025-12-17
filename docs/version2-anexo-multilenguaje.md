# Anexo: Soporte Multi-Lenguaje con Patrón Strategy

**Arquitectura polimórfica para parsing/rewriting de contratos por lenguaje**

---

## 1. Principio de Diseño

> **Un Strategy por lenguaje, un Pipeline común**

El sistema de contratos debe soportar múltiples lenguajes (C++, Python, TypeScript, etc.) sin duplicar lógica. Usamos el **patrón Strategy** para encapsular las particularidades de cada lenguaje.

```
┌─────────────────────────────────────────────────────────────┐
│                    ContractDiscovery                        │
│                    (Pipeline común)                         │
├─────────────────────────────────────────────────────────────┤
│  Nivel 1: find_contract_block()    ──┐                      │
│  Nivel 2: parse_known_patterns()   ──┼── Delegado a Strategy│
│  Nivel 3: LLM (común)                │                      │
│  Nivel 4: Análisis estático        ──┘                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   LanguageRegistry                          │
│              (Selecciona Strategy por extensión)            │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │   Cpp    │    │  Python  │    │   TS     │
    │ Strategy │    │ Strategy │    │ Strategy │
    └──────────┘    └──────────┘    └──────────┘
```

---

## 2. Interfaz Base (Abstract Strategy)

```python
# code_map/contracts/languages/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from ..schema import ContractData


@dataclass
class ContractBlock:
    """Bloque de contrato encontrado en el código."""
    start_line: int
    end_line: int
    content: str
    raw_text: str  # Texto original incluyendo delimitadores


@dataclass
class CommentBlock:
    """Bloque de comentario/docstring asociado a un símbolo."""
    start_line: int
    end_line: int
    content: str
    style: str  # 'line', 'block', 'docstring'


class LanguageStrategy(ABC):
    """
    Strategy base para parsing/rewriting de contratos por lenguaje.

    Cada implementación concreta maneja:
    - Sintaxis de comentarios específica del lenguaje
    - Patrones de documentación conocidos (Doxygen, Google style, etc.)
    - Ubicación canónica para insertar contratos
    - Formato de salida al reescribir
    """

    # ─────────────────────────────────────────────────────────────
    # Propiedades abstractas
    # ─────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def language_id(self) -> str:
        """
        Identificador único del lenguaje.
        Ejemplos: 'cpp', 'python', 'typescript', 'java'
        """
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> Tuple[str, ...]:
        """
        Extensiones de archivo soportadas.
        Ejemplos: ('.cpp', '.hpp', '.h') para C++
        """
        pass

    @property
    @abstractmethod
    def comment_styles(self) -> dict:
        """
        Estilos de comentario soportados.
        Ejemplo para C++:
        {
            'line': '//',
            'block_start': '/*',
            'block_end': '*/',
            'doc_start': '/**',
        }
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Métodos abstractos: Parsing
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    def find_contract_block(
        self,
        source: str,
        symbol_line: int
    ) -> Optional[ContractBlock]:
        """
        Nivel 1: Busca bloque @aegis-contract cerca del símbolo.

        Args:
            source: Código fuente completo del archivo
            symbol_line: Línea donde está definido el símbolo (1-indexed)

        Returns:
            ContractBlock si encuentra @aegis-contract, None si no
        """
        pass

    @abstractmethod
    def find_comment_block(
        self,
        source: str,
        symbol_line: int
    ) -> Optional[CommentBlock]:
        """
        Encuentra el bloque de comentario/docstring asociado a un símbolo.

        Args:
            source: Código fuente completo
            symbol_line: Línea del símbolo

        Returns:
            CommentBlock con el comentario encontrado, None si no hay
        """
        pass

    @abstractmethod
    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """
        Nivel 2: Extrae contrato de patrones conocidos del lenguaje.

        Patrones por lenguaje:
        - C++: Doxygen (@pre, @post, @invariant, @throws)
        - Python: Google style, NumPy style, Sphinx
        - TypeScript: JSDoc (@throws, @returns)

        Args:
            comment: Bloque de comentario a analizar

        Returns:
            ContractData con los campos extraídos (puede estar parcialmente vacío)
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Métodos abstractos: Rewriting
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    def insert_contract_block(
        self,
        source: str,
        symbol_line: int,
        contract: ContractData
    ) -> str:
        """
        Inserta nuevo bloque @aegis-contract en ubicación canónica.

        Ubicación canónica por lenguaje:
        - C++: Comentario inmediatamente antes de la declaración
        - Python: Inicio del docstring (antes del texto existente)

        Args:
            source: Código fuente original
            symbol_line: Línea del símbolo objetivo
            contract: Datos del contrato a insertar

        Returns:
            Código fuente modificado con el bloque insertado
        """
        pass

    @abstractmethod
    def update_contract_block(
        self,
        source: str,
        block: ContractBlock,
        contract: ContractData
    ) -> str:
        """
        Actualiza bloque @aegis-contract existente.

        IMPORTANTE: Solo modifica el contenido entre los delimitadores,
        preservando indentación y formato del resto del archivo.

        Args:
            source: Código fuente original
            block: Bloque existente a reemplazar
            contract: Nuevos datos del contrato

        Returns:
            Código fuente con el bloque actualizado
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Métodos concretos (compartidos)
    # ─────────────────────────────────────────────────────────────

    def format_contract_yaml(self, contract: ContractData, indent: str = "") -> str:
        """
        Formatea ContractData como YAML para embeber en comentario.

        Args:
            contract: Datos a formatear
            indent: Prefijo de indentación para cada línea

        Returns:
            String YAML formateado
        """
        lines = []

        if contract.thread_safety:
            lines.append(f"thread_safety: {contract.thread_safety.value}")

        if contract.lifecycle:
            lines.append(f"lifecycle: {contract.lifecycle}")

        if contract.invariants:
            lines.append("invariants:")
            for inv in contract.invariants:
                lines.append(f"  - {inv}")

        if contract.preconditions:
            lines.append("preconditions:")
            for pre in contract.preconditions:
                lines.append(f"  - {pre}")

        if contract.postconditions:
            lines.append("postconditions:")
            for post in contract.postconditions:
                lines.append(f"  - {post}")

        if contract.errors:
            lines.append("errors:")
            for err in contract.errors:
                lines.append(f"  - {err}")

        if contract.dependencies:
            lines.append("dependencies:")
            for dep in contract.dependencies:
                lines.append(f"  - {dep}")

        if contract.evidence:
            lines.append("evidence:")
            for ev in contract.evidence:
                lines.append(f"  - {ev.type}: {ev.reference}")
                if ev.policy.value != "optional":
                    lines.append(f"    policy: {ev.policy.value}")

        return "\n".join(f"{indent}{line}" for line in lines)

    def detect_indentation(self, source: str, line_number: int) -> str:
        """
        Detecta la indentación usada en una línea específica.

        Args:
            source: Código fuente
            line_number: Número de línea (1-indexed)

        Returns:
            String de indentación (espacios/tabs)
        """
        lines = source.splitlines()
        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            return line[:len(line) - len(line.lstrip())]
        return ""
```

---

## 3. Implementación C++

```python
# code_map/contracts/languages/cpp.py

import re
from typing import Optional, Tuple
from .base import LanguageStrategy, ContractBlock, CommentBlock
from ..schema import ContractData, ThreadSafety, EvidenceItem, EvidencePolicy


class CppLanguageStrategy(LanguageStrategy):
    """Strategy para C/C++."""

    # ─────────────────────────────────────────────────────────────
    # Propiedades
    # ─────────────────────────────────────────────────────────────

    @property
    def language_id(self) -> str:
        return "cpp"

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".cpp", ".hpp", ".h", ".cc", ".cxx", ".hxx", ".c")

    @property
    def comment_styles(self) -> dict:
        return {
            "line": "//",
            "block_start": "/*",
            "block_end": "*/",
            "doc_start": "/**",
        }

    # ─────────────────────────────────────────────────────────────
    # Patrones Doxygen
    # ─────────────────────────────────────────────────────────────

    DOXYGEN_PATTERNS = {
        "preconditions": re.compile(r"@pre\s+(.+?)(?=@|\*/|\n\s*\*\s*@|\Z)", re.DOTALL),
        "postconditions": re.compile(r"@post\s+(.+?)(?=@|\*/|\n\s*\*\s*@|\Z)", re.DOTALL),
        "invariants": re.compile(r"@invariant\s+(.+?)(?=@|\*/|\n\s*\*\s*@|\Z)", re.DOTALL),
        "errors": re.compile(r"@throws?\s+(\S+)\s+(.+?)(?=@|\*/|\n\s*\*\s*@|\Z)", re.DOTALL),
    }

    THREAD_SAFETY_PATTERNS = [
        (re.compile(r"thread[_-]?safe", re.I), ThreadSafety.SAFE),
        (re.compile(r"not\s+thread[_-]?safe", re.I), ThreadSafety.NOT_SAFE),
        (re.compile(r"safe\s+after\s+start", re.I), ThreadSafety.SAFE_AFTER_START),
        (re.compile(r"immutable", re.I), ThreadSafety.IMMUTABLE),
    ]

    # ─────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────

    def find_contract_block(
        self, source: str, symbol_line: int
    ) -> Optional[ContractBlock]:
        """Busca @aegis-contract-begin/end antes del símbolo."""
        lines = source.splitlines()

        # Buscar hacia arriba desde symbol_line
        start_marker = "@aegis-contract-begin"
        end_marker = "@aegis-contract-end"

        start_idx = None
        end_idx = None

        # Buscar en las 20 líneas anteriores al símbolo
        search_start = max(0, symbol_line - 20)
        for i in range(symbol_line - 1, search_start - 1, -1):
            line = lines[i] if i < len(lines) else ""
            if end_marker in line and end_idx is None:
                end_idx = i
            if start_marker in line:
                start_idx = i
                break

        if start_idx is not None and end_idx is not None and start_idx < end_idx:
            # Extraer contenido entre marcadores
            content_lines = []
            for i in range(start_idx + 1, end_idx):
                line = lines[i]
                # Limpiar prefijo de comentario
                cleaned = line.strip()
                if cleaned.startswith("//"):
                    cleaned = cleaned[2:].strip()
                elif cleaned.startswith("*"):
                    cleaned = cleaned[1:].strip()
                content_lines.append(cleaned)

            return ContractBlock(
                start_line=start_idx + 1,
                end_line=end_idx + 1,
                content="\n".join(content_lines),
                raw_text="\n".join(lines[start_idx:end_idx + 1])
            )

        return None

    def find_comment_block(
        self, source: str, symbol_line: int
    ) -> Optional[CommentBlock]:
        """Encuentra comentario Doxygen/normal antes del símbolo."""
        lines = source.splitlines()

        # Buscar hacia arriba desde symbol_line - 1
        end_idx = symbol_line - 2  # 0-indexed, línea anterior
        if end_idx < 0:
            return None

        # Detectar tipo de comentario
        comment_lines = []
        style = None
        start_idx = end_idx

        # Caso 1: Comentario de bloque /** ... */
        if lines[end_idx].strip().endswith("*/"):
            style = "block"
            # Buscar inicio del bloque
            for i in range(end_idx, -1, -1):
                line = lines[i]
                comment_lines.insert(0, line)
                if "/**" in line or "/*" in line:
                    start_idx = i
                    break

        # Caso 2: Comentarios de línea // ...
        elif lines[end_idx].strip().startswith("//"):
            style = "line"
            for i in range(end_idx, -1, -1):
                line = lines[i].strip()
                if line.startswith("//"):
                    comment_lines.insert(0, lines[i])
                    start_idx = i
                else:
                    break

        if not comment_lines:
            return None

        # Limpiar contenido
        content = self._clean_comment_content(comment_lines, style)

        return CommentBlock(
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            content=content,
            style=style
        )

    def _clean_comment_content(self, lines: list, style: str) -> str:
        """Limpia el contenido del comentario eliminando prefijos."""
        cleaned = []
        for line in lines:
            text = line.strip()
            if style == "line":
                if text.startswith("//"):
                    text = text[2:].strip()
            elif style == "block":
                text = text.lstrip("/*").rstrip("*/").strip()
                if text.startswith("*"):
                    text = text[1:].strip()
            cleaned.append(text)
        return "\n".join(cleaned)

    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """Extrae contrato de patrones Doxygen."""
        content = comment.content
        contract = ContractData(confidence=0.8, source_level=2)

        # Precondiciones
        for match in self.DOXYGEN_PATTERNS["preconditions"].finditer(content):
            contract.preconditions.append(match.group(1).strip())

        # Postcondiciones
        for match in self.DOXYGEN_PATTERNS["postconditions"].finditer(content):
            contract.postconditions.append(match.group(1).strip())

        # Invariantes
        for match in self.DOXYGEN_PATTERNS["invariants"].finditer(content):
            contract.invariants.append(match.group(1).strip())

        # Errores/excepciones
        for match in self.DOXYGEN_PATTERNS["errors"].finditer(content):
            exception_type = match.group(1)
            description = match.group(2).strip()
            contract.errors.append(f"{exception_type}: {description}")

        # Thread safety (buscar en todo el comentario)
        for pattern, safety in self.THREAD_SAFETY_PATTERNS:
            if pattern.search(content):
                contract.thread_safety = safety
                break

        return contract

    # ─────────────────────────────────────────────────────────────
    # Rewriting
    # ─────────────────────────────────────────────────────────────

    def insert_contract_block(
        self, source: str, symbol_line: int, contract: ContractData
    ) -> str:
        """Inserta bloque @aegis-contract antes del símbolo."""
        lines = source.splitlines()
        indent = self.detect_indentation(source, symbol_line)

        # Generar bloque de contrato
        block_lines = [
            f"{indent}// @aegis-contract-begin",
        ]

        yaml_content = self.format_contract_yaml(contract, indent=f"{indent}// ")
        block_lines.extend(yaml_content.splitlines())

        block_lines.append(f"{indent}// @aegis-contract-end")

        # Insertar antes del símbolo
        insert_idx = symbol_line - 1  # 0-indexed

        # Buscar si hay comentario existente para insertar después
        if insert_idx > 0:
            prev_line = lines[insert_idx - 1].strip()
            if prev_line.endswith("*/") or prev_line.startswith("//"):
                # Hay comentario, insertar entre comentario y símbolo
                pass

        new_lines = lines[:insert_idx] + block_lines + lines[insert_idx:]
        return "\n".join(new_lines)

    def update_contract_block(
        self, source: str, block: ContractBlock, contract: ContractData
    ) -> str:
        """Actualiza bloque existente preservando formato."""
        lines = source.splitlines()

        # Detectar indentación del bloque existente
        first_line = lines[block.start_line - 1]
        indent = first_line[:len(first_line) - len(first_line.lstrip())]

        # Generar nuevo contenido
        new_block_lines = [
            f"{indent}// @aegis-contract-begin",
        ]

        yaml_content = self.format_contract_yaml(contract, indent=f"{indent}// ")
        new_block_lines.extend(yaml_content.splitlines())

        new_block_lines.append(f"{indent}// @aegis-contract-end")

        # Reemplazar líneas del bloque
        start_idx = block.start_line - 1
        end_idx = block.end_line  # Exclusivo

        new_lines = lines[:start_idx] + new_block_lines + lines[end_idx:]
        return "\n".join(new_lines)
```

---

## 4. Implementación Python

```python
# code_map/contracts/languages/python.py

import re
from typing import Optional, Tuple
from .base import LanguageStrategy, ContractBlock, CommentBlock
from ..schema import ContractData, ThreadSafety


class PythonLanguageStrategy(LanguageStrategy):
    """Strategy para Python."""

    @property
    def language_id(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".py", ".pyi")

    @property
    def comment_styles(self) -> dict:
        return {
            "line": "#",
            "docstring_single": "'''",
            "docstring_double": '"""',
        }

    # ─────────────────────────────────────────────────────────────
    # Patrones Google Style / NumPy
    # ─────────────────────────────────────────────────────────────

    GOOGLE_STYLE_SECTIONS = {
        "Args": "args",
        "Arguments": "args",
        "Returns": "returns",
        "Yields": "yields",
        "Raises": "errors",
        "Attributes": "attributes",
        "Note": "notes",
        "Notes": "notes",
        "Example": "examples",
        "Examples": "examples",
    }

    # ─────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────

    def find_contract_block(
        self, source: str, symbol_line: int
    ) -> Optional[ContractBlock]:
        """Busca @aegis-contract dentro del docstring del símbolo."""
        lines = source.splitlines()

        # En Python, el contrato está DENTRO del docstring, no antes
        # Buscar inicio de docstring después del símbolo
        docstring_start = None
        docstring_end = None
        quote_style = None

        for i in range(symbol_line - 1, min(symbol_line + 5, len(lines))):
            line = lines[i].strip()
            if '"""' in line or "'''" in line:
                quote_style = '"""' if '"""' in line else "'''"
                docstring_start = i

                # ¿Es docstring de una línea?
                if line.count(quote_style) >= 2:
                    docstring_end = i
                    break

                # Buscar cierre
                for j in range(i + 1, len(lines)):
                    if quote_style in lines[j]:
                        docstring_end = j
                        break
                break

        if docstring_start is None or docstring_end is None:
            return None

        # Buscar @aegis-contract dentro del docstring
        start_marker = "@aegis-contract-begin"
        end_marker = "@aegis-contract-end"

        contract_start = None
        contract_end = None

        for i in range(docstring_start, docstring_end + 1):
            line = lines[i]
            if start_marker in line:
                contract_start = i
            if end_marker in line:
                contract_end = i
                break

        if contract_start is not None and contract_end is not None:
            content_lines = []
            for i in range(contract_start + 1, contract_end):
                content_lines.append(lines[i].strip())

            return ContractBlock(
                start_line=contract_start + 1,
                end_line=contract_end + 1,
                content="\n".join(content_lines),
                raw_text="\n".join(lines[contract_start:contract_end + 1])
            )

        return None

    def find_comment_block(
        self, source: str, symbol_line: int
    ) -> Optional[CommentBlock]:
        """Encuentra el docstring de una función/clase."""
        lines = source.splitlines()

        # Buscar docstring después del símbolo (def/class)
        for i in range(symbol_line - 1, min(symbol_line + 3, len(lines))):
            line = lines[i].strip()

            for quote in ['"""', "'''"]:
                if quote in line:
                    start_idx = i

                    # Docstring de una línea
                    if line.count(quote) >= 2:
                        content = line.strip(quote).strip()
                        return CommentBlock(
                            start_line=i + 1,
                            end_line=i + 1,
                            content=content,
                            style="docstring"
                        )

                    # Docstring multilínea
                    content_lines = [line.replace(quote, "").strip()]
                    for j in range(i + 1, len(lines)):
                        end_line = lines[j]
                        if quote in end_line:
                            content_lines.append(end_line.replace(quote, "").strip())
                            return CommentBlock(
                                start_line=i + 1,
                                end_line=j + 1,
                                content="\n".join(content_lines),
                                style="docstring"
                            )
                        content_lines.append(end_line.strip())

        return None

    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """Extrae contrato de Google style docstring."""
        content = comment.content
        contract = ContractData(confidence=0.8, source_level=2)

        # Buscar sección Raises para errores
        raises_match = re.search(
            r"Raises:\s*\n((?:\s+\S.*\n?)+)",
            content,
            re.MULTILINE
        )
        if raises_match:
            raises_content = raises_match.group(1)
            # Parsear cada excepción
            for line in raises_content.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("Raises"):
                    contract.errors.append(line)

        # Buscar Note/Notes para thread safety y otros
        notes_match = re.search(
            r"Notes?:\s*\n((?:\s+\S.*\n?)+)",
            content,
            re.MULTILINE
        )
        if notes_match:
            notes_content = notes_match.group(1).lower()
            if "thread-safe" in notes_content or "threadsafe" in notes_content:
                if "not thread" in notes_content:
                    contract.thread_safety = ThreadSafety.NOT_SAFE
                elif "after start" in notes_content:
                    contract.thread_safety = ThreadSafety.SAFE_AFTER_START
                else:
                    contract.thread_safety = ThreadSafety.SAFE

        # Buscar precondiciones en Args (patrón: "Must not be None")
        args_match = re.search(
            r"Args:\s*\n((?:\s+\S.*\n?)+)",
            content,
            re.MULTILINE
        )
        if args_match:
            args_content = args_match.group(1)
            if "must not be none" in args_content.lower():
                contract.preconditions.append("input is not None")
            if "must be" in args_content.lower():
                # Extraer la condición
                must_match = re.search(r"must be ([^.]+)", args_content, re.I)
                if must_match:
                    contract.preconditions.append(f"input must be {must_match.group(1)}")

        return contract

    # ─────────────────────────────────────────────────────────────
    # Rewriting
    # ─────────────────────────────────────────────────────────────

    def insert_contract_block(
        self, source: str, symbol_line: int, contract: ContractData
    ) -> str:
        """Inserta @aegis-contract al inicio del docstring."""
        lines = source.splitlines()

        # Encontrar docstring existente
        docstring_info = self._find_docstring_location(lines, symbol_line)

        if docstring_info:
            # Insertar dentro del docstring existente
            return self._insert_into_existing_docstring(
                lines, docstring_info, contract
            )
        else:
            # Crear nuevo docstring
            return self._create_new_docstring(lines, symbol_line, contract)

    def _find_docstring_location(self, lines: list, symbol_line: int) -> Optional[dict]:
        """Encuentra la ubicación del docstring si existe."""
        for i in range(symbol_line - 1, min(symbol_line + 3, len(lines))):
            line = lines[i].strip()
            for quote in ['"""', "'''"]:
                if line.startswith(quote) or (line.endswith(":") is False and quote in line):
                    # Encontrar fin del docstring
                    if line.count(quote) >= 2:
                        return {"start": i, "end": i, "quote": quote, "single_line": True}
                    for j in range(i + 1, len(lines)):
                        if quote in lines[j]:
                            return {"start": i, "end": j, "quote": quote, "single_line": False}
        return None

    def _insert_into_existing_docstring(
        self, lines: list, docstring_info: dict, contract: ContractData
    ) -> str:
        """Inserta bloque de contrato en docstring existente."""
        start = docstring_info["start"]
        quote = docstring_info["quote"]
        indent = self.detect_indentation("\n".join(lines), start + 1)
        inner_indent = indent + "    "

        # Generar bloque de contrato
        contract_block = [
            f"{inner_indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=inner_indent)
        contract_block.extend(yaml_content.splitlines())
        contract_block.append(f"{inner_indent}@aegis-contract-end")
        contract_block.append("")  # Línea vacía antes del resto del docstring

        if docstring_info["single_line"]:
            # Convertir a multilínea
            original_content = lines[start].strip().strip(quote).strip()
            new_lines = lines[:start]
            new_lines.append(f'{indent}{quote}')
            new_lines.extend(contract_block)
            if original_content:
                new_lines.append(f"{inner_indent}{original_content}")
            new_lines.append(f'{indent}{quote}')
            new_lines.extend(lines[start + 1:])
        else:
            # Insertar después de la línea de apertura
            new_lines = lines[:start + 1]
            new_lines.extend(contract_block)
            new_lines.extend(lines[start + 1:])

        return "\n".join(new_lines)

    def _create_new_docstring(
        self, lines: list, symbol_line: int, contract: ContractData
    ) -> str:
        """Crea nuevo docstring con contrato."""
        # Encontrar línea después de def/class
        insert_idx = symbol_line  # Después del símbolo
        indent = self.detect_indentation("\n".join(lines), symbol_line)
        inner_indent = indent + "    "

        docstring_lines = [
            f'{inner_indent}"""',
            f"{inner_indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=inner_indent)
        docstring_lines.extend(yaml_content.splitlines())
        docstring_lines.append(f"{inner_indent}@aegis-contract-end")
        docstring_lines.append(f'{inner_indent}"""')

        new_lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
        return "\n".join(new_lines)

    def update_contract_block(
        self, source: str, block: ContractBlock, contract: ContractData
    ) -> str:
        """Actualiza bloque existente dentro del docstring."""
        lines = source.splitlines()

        # Detectar indentación
        first_line = lines[block.start_line - 1]
        indent = first_line[:len(first_line) - len(first_line.lstrip())]

        # Generar nuevo contenido
        new_block_lines = [
            f"{indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=indent)
        new_block_lines.extend(yaml_content.splitlines())
        new_block_lines.append(f"{indent}@aegis-contract-end")

        # Reemplazar
        start_idx = block.start_line - 1
        end_idx = block.end_line

        new_lines = lines[:start_idx] + new_block_lines + lines[end_idx:]
        return "\n".join(new_lines)
```

---

## 5. Registry de Strategies

```python
# code_map/contracts/languages/registry.py

from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import LanguageStrategy


class LanguageRegistry:
    """
    Registry central de Language Strategies.

    Patrón similar a analyzer_registry.py de AEGIS v1.
    Permite registrar strategies y obtenerlos por extensión de archivo.
    """

    _strategies: Dict[str, LanguageStrategy] = {}
    _extension_map: Dict[str, str] = {}

    @classmethod
    def register(cls, strategy_class: Type[LanguageStrategy]) -> Type[LanguageStrategy]:
        """
        Registra una strategy. Puede usarse como decorador.

        @LanguageRegistry.register
        class MyLanguageStrategy(LanguageStrategy):
            ...
        """
        instance = strategy_class()
        cls._strategies[instance.language_id] = instance

        for ext in instance.file_extensions:
            ext_lower = ext.lower()
            if ext_lower in cls._extension_map:
                existing = cls._extension_map[ext_lower]
                if existing != instance.language_id:
                    # Warning: extensión ya registrada por otro lenguaje
                    pass
            cls._extension_map[ext_lower] = instance.language_id

        return strategy_class

    @classmethod
    def get_for_file(cls, path: Path) -> Optional[LanguageStrategy]:
        """Obtiene strategy apropiado para un archivo por su extensión."""
        ext = path.suffix.lower()
        lang_id = cls._extension_map.get(ext)
        return cls._strategies.get(lang_id) if lang_id else None

    @classmethod
    def get_by_id(cls, language_id: str) -> Optional[LanguageStrategy]:
        """Obtiene strategy por identificador de lenguaje."""
        return cls._strategies.get(language_id)

    @classmethod
    def supported_extensions(cls) -> List[str]:
        """Lista todas las extensiones soportadas."""
        return list(cls._extension_map.keys())

    @classmethod
    def supported_languages(cls) -> List[str]:
        """Lista todos los lenguajes soportados."""
        return list(cls._strategies.keys())

    @classmethod
    def clear(cls) -> None:
        """Limpia el registry. Útil para tests."""
        cls._strategies.clear()
        cls._extension_map.clear()


# ─────────────────────────────────────────────────────────────
# Auto-registro al importar el paquete
# ─────────────────────────────────────────────────────────────

def _auto_register():
    """Registra strategies por defecto."""
    from .cpp import CppLanguageStrategy
    from .python import PythonLanguageStrategy

    LanguageRegistry.register(CppLanguageStrategy)
    LanguageRegistry.register(PythonLanguageStrategy)


_auto_register()
```

---

## 6. Uso en Discovery Pipeline

```python
# code_map/contracts/discovery.py (fragmento)

from pathlib import Path
from .languages.registry import LanguageRegistry
from .schema import ContractData


class ContractDiscovery:
    """Orquestador del pipeline de descubrimiento."""

    def discover(
        self,
        file_path: Path,
        symbol_line: int,
        enable_llm: bool = True
    ) -> ContractData:
        """
        Ejecuta pipeline de descubrimiento para un símbolo.

        Args:
            file_path: Archivo a analizar
            symbol_line: Línea del símbolo
            enable_llm: Si True y Ollama disponible, usa Nivel 3
        """
        # Obtener strategy para el lenguaje
        strategy = LanguageRegistry.get_for_file(file_path)

        if not strategy:
            # Lenguaje no soportado
            return ContractData(
                confidence=0.0,
                source_level=5,
                confidence_notes=f"Lenguaje no soportado: {file_path.suffix}"
            )

        source = file_path.read_text(encoding="utf-8")

        # ─────────────────────────────────────────────────────
        # Nivel 1: Bloques @aegis-contract
        # ─────────────────────────────────────────────────────
        block = strategy.find_contract_block(source, symbol_line)
        if block:
            contract = self._parse_aegis_yaml(block.content)
            contract.confidence = 1.0
            contract.source_level = 1
            contract.file_path = file_path
            contract.start_line = block.start_line
            contract.end_line = block.end_line
            return contract

        # ─────────────────────────────────────────────────────
        # Nivel 2: Patrones conocidos (delegado a strategy)
        # ─────────────────────────────────────────────────────
        comment = strategy.find_comment_block(source, symbol_line)
        if comment:
            contract = strategy.parse_known_patterns(comment)
            if not contract.is_empty():
                contract.file_path = file_path
                contract.start_line = comment.start_line
                contract.end_line = comment.end_line
                return contract

        # ─────────────────────────────────────────────────────
        # Nivel 3: LLM (común para todos los lenguajes)
        # ─────────────────────────────────────────────────────
        if enable_llm and self._is_ollama_available():
            contract = self._extract_with_llm(source, symbol_line, strategy)
            if not contract.is_empty():
                return contract

        # ─────────────────────────────────────────────────────
        # Nivel 4: Análisis estático (común con hints del strategy)
        # ─────────────────────────────────────────────────────
        contract = self._extract_from_static_analysis(source, symbol_line)
        if not contract.is_empty():
            return contract

        # ─────────────────────────────────────────────────────
        # Nivel 5: Sin contrato
        # ─────────────────────────────────────────────────────
        return ContractData(
            confidence=0.0,
            source_level=5,
            file_path=file_path
        )
```

---

## 7. Extensibilidad: Añadir Nuevo Lenguaje

Para añadir soporte de un nuevo lenguaje (ej: TypeScript):

```python
# code_map/contracts/languages/typescript.py

from .base import LanguageStrategy
from .registry import LanguageRegistry


@LanguageRegistry.register
class TypeScriptLanguageStrategy(LanguageStrategy):

    @property
    def language_id(self) -> str:
        return "typescript"

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".ts", ".tsx", ".mts", ".cts")

    @property
    def comment_styles(self) -> dict:
        return {
            "line": "//",
            "block_start": "/*",
            "block_end": "*/",
            "jsdoc_start": "/**",
        }

    # Implementar métodos abstractos...
    # Patrones JSDoc: @throws, @returns, @param, etc.
```

El decorador `@LanguageRegistry.register` hace el registro automático.

---

## 8. Checklist de Implementación

```
[ ] Fase 1: Base
    [ ] Crear code_map/contracts/languages/__init__.py
    [ ] Crear code_map/contracts/languages/base.py
    [ ] Crear code_map/contracts/languages/registry.py
    [ ] Tests unitarios para registry

[ ] Fase 2: C++ Strategy
    [ ] Crear code_map/contracts/languages/cpp.py
    [ ] Implementar find_contract_block
    [ ] Implementar find_comment_block
    [ ] Implementar parse_known_patterns (Doxygen)
    [ ] Implementar insert_contract_block
    [ ] Implementar update_contract_block
    [ ] Tests con proyecto Actia

[ ] Fase 3: Python Strategy
    [ ] Crear code_map/contracts/languages/python.py
    [ ] Implementar métodos para docstrings
    [ ] Implementar parse_known_patterns (Google style)
    [ ] Tests con código Python real

[ ] Fase 4: Integración
    [ ] Integrar registry en discovery.py
    [ ] Actualizar API endpoints
    [ ] Tests end-to-end
```
