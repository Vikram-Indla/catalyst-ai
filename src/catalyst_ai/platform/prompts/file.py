"""A prompt file is a header block and named `[section]` blocks; filling replaces tokens."""

import re
from dataclasses import dataclass
from pathlib import Path

HEADER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.S)
SECTION = re.compile(r"^\[(?P<name>[^\]\n]+)\]\n", re.M)
PLACEHOLDER = re.compile(r"\{(?P<name>[a-z_]+)\}")


def fill(template: str, values: dict[str, str]) -> str:
    """Replace every `{name}` token with its value; an unknown token is a defect, not a blank."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in values:
            message = f"prompt placeholder {name!r} has no value"
            raise KeyError(message)
        return values[name]

    return PLACEHOLDER.sub(_replace, template)


@dataclass(frozen=True)
class PromptFile:
    """The parsed file: header key-values and section texts by name."""

    header: dict[str, str]
    sections: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "PromptFile":
        """Parse the file; a missing header or a duplicate section is a defect."""
        text = path.read_text(encoding="utf-8")
        match = HEADER.match(text)
        if match is None:
            message = f"{path} lacks the header block"
            raise ValueError(message)
        header = {}
        for line in match.group("body").splitlines():
            key, _, value = line.partition(":")
            header[key.strip()] = value.strip()
        sections: dict[str, str] = {}
        rest = text[match.end() :]
        starts = list(SECTION.finditer(rest))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(rest)
            name = start.group("name")
            if name in sections:
                message = f"{path} defines section {name!r} twice"
                raise ValueError(message)
            sections[name] = rest[start.end() : end].strip()
        return cls(header=header, sections=sections)

    def section(self, name: str) -> str:
        """Return the text of one section; a missing section is a defect."""
        try:
            return self.sections[name]
        except KeyError as error:
            message = f"no section {name!r} in the prompt file"
            raise KeyError(message) from error
