"""Safe Boolean population rules built from marker-positive predicates."""

import re


TOKEN = re.compile(r"\s*(?:(AND|OR|NOT)|(\()|(\))|([A-Za-z0-9_.-]+)([+-]))", re.I)


def evaluate_population(dataframe, rule, thresholds):
    """Evaluate a Boolean marker rule without executing arbitrary code."""
    tokens, position = [], 0
    while position < len(rule):
        match = TOKEN.match(rule, position)
        if not match:
            raise ValueError(f"Invalid population rule near: {rule[position:]}")
        operator, left, right, marker, sign = match.groups()
        if operator:
            tokens.append(operator.upper())
        elif left or right:
            tokens.append(left or right)
        else:
            column = f"{marker}_sum"
            if column not in dataframe or marker not in thresholds:
                raise ValueError(f"Unknown marker or threshold: {marker}")
            value = dataframe[column] > thresholds[marker]
            tokens.append(value if sign == "+" else ~value)
        position = match.end()

    precedence = {"OR": 1, "AND": 2, "NOT": 3}
    output, operators = [], []
    for token in tokens:
        if not isinstance(token, str):
            output.append(token)
        elif token == "(":
            operators.append(token)
        elif token == ")":
            while operators and operators[-1] != "(": output.append(operators.pop())
            if not operators: raise ValueError("Unbalanced parentheses")
            operators.pop()
        else:
            while operators and operators[-1] != "(" and precedence[operators[-1]] >= precedence[token]: output.append(operators.pop())
            operators.append(token)
    while operators:
        if operators[-1] == "(": raise ValueError("Unbalanced parentheses")
        output.append(operators.pop())
    stack = []
    for token in output:
        if not isinstance(token, str): stack.append(token)
        elif token == "NOT": stack.append(~stack.pop())
        else:
            right, left = stack.pop(), stack.pop()
            stack.append(left & right if token == "AND" else left | right)
    if len(stack) != 1: raise ValueError("Incomplete population rule")
    return stack[0]

