import re

def normalize_cpf(raw: str) -> str:
    return re.sub(r"\D+", "", raw or "")

def invalid_cpf_sequence(cpf: str) -> bool:
    return cpf == cpf[0] * len(cpf)

def calculate_cpf_check_digits(cpf9: str) -> str:
    def cd(slice_, factor):
        s = sum(int(d) * (factor - i) for i, d in enumerate(slice_))
        check = (s * 10) % 11
        return str(check if check < 10 else 0)
    return cd(cpf9, 10) + cd(cpf9 + cd(cpf9, 10), 11)

def is_valid_cpf(cpf: str) -> bool:
    cpf11 = normalize_cpf(cpf)
    if len(cpf11) != 11 or invalid_cpf_sequence(cpf11):
        return False
    return calculate_cpf_check_digits(cpf11[:9]) == cpf11[-2:]
