"""Construction de la commande du runner d'entraînement externe (allowlisté).

Le cockpit n'entraîne pas : il appelle un runner externe en **argv liste**
(jamais `shell=True`, jamais `systemctl`). La forme est figée :

    [python, "-m", <TRAIN_RUNNER>, "--dataset", ..., "--base-model", ...,
     "--method", ..., "--output", ...]

`TRAIN_RUNNER` est un nom de module (pas une chaîne shell). Si vide → dry-run
(aucun sous-process). Les dépendances lourdes (peft/transformers/bitsandbytes)
vivent dans ce runner externe, pas dans le cockpit.
"""

import sys


def build_runner_argv(
    runner: str, dataset_path: str, base_model: str, method: str, output_dir: str
) -> list[str]:
    if not runner:
        raise ValueError("runner vide")
    # argv en liste, exécutable Python courant + module allowlisté. Jamais shell.
    return [
        sys.executable,
        "-m",
        runner,
        "--dataset",
        dataset_path,
        "--base-model",
        base_model,
        "--method",
        method,
        "--output",
        output_dir,
    ]
