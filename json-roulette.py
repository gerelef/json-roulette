#!/usr/bin/env python3.12
import argparse
import functools
import json
import os
import random
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def decide(percentage: float) -> bool:
    """
    :param percentage: percentage <= 1.0
    """
    assert percentage <= 1.0
    return round(random.uniform(0, 1), 3) <= percentage


def field_roulette(json: dict) -> bool:
    """
    Do nothing, remove any field, or return True to add a field.
    :return: whether to add a field.
    """
    edit_field = random.randint(1, 15) == 1
    remove_field = random.randint(1, 2) == 1
    if edit_field and remove_field:
        del json[random.choice(list(json.keys()))]
        return False

    return edit_field


def generate_random_string(nullability_chance) -> str | None:
    if decide(nullability_chance):
        return None
    return "".join(random.choices(string.ascii_letters, k=random.randint(3, 9)))


def generate_random_int(nullability_chance) -> int | None:
    if decide(nullability_chance):
        return None
    return random.randint(-999, 10000)


def generate_random_double(nullability_chance) -> float | None:
    if decide(nullability_chance):
        return None
    return random.uniform(-1000, 1000)


def generate_random_bool(nullability_chance) -> bool | None:
    if decide(nullability_chance):
        return None
    return decide(random.uniform(0.2, 0.8))


def generate_random_jfield(*generators: Callable[[], object], **kwargs) -> tuple[str, ...]:
    return random.choice(words), random.choice(generators)(**kwargs)


def generate_jobj(
        primitive_generator: Callable,
        composite_generator: Callable,
        length_low: int,
        length_high: int,
        nested_chance: float,
        nested_max_depth: int,
        current_depth: int,
        nullability_chance: float) -> dict | None:
    if decide(nullability_chance):
        return None

    out = {}
    jobj_length = random.randint(length_low, length_high)
    for i in range(jobj_length):
        key, value = primitive_generator()
        if current_depth < nested_max_depth and decide(nested_chance):
            key, value = composite_generator(
                primitive_generator=primitive_generator,
                composite_generator=composite_generator,
                length_low=length_low,
                length_high=length_high,
                nested_chance=nested_chance,
                nested_max_depth=nested_max_depth,
                current_depth=current_depth + 1,
            )
        out[key] = value
    return out


def generate_jarr(
        primitive_generator: Callable,
        composite_generator: Callable,
        length_low: int,
        length_high: int,
        nested_chance: float,
        nested_max_depth: int,
        current_depth: int,
        nullability_chance: float) -> list | None:
    if decide(nullability_chance):
        return None
    out = []
    jobj_length = random.randint(length_low, length_high)
    for i in range(jobj_length):
        _, value = primitive_generator()
        if current_depth < nested_max_depth and decide(nested_chance):
            _, value = composite_generator(
                primitive_generator=primitive_generator,
                composite_generator=composite_generator,
                length_low=length_low,
                length_high=length_high,
                nested_chance=nested_chance,
                nested_max_depth=nested_max_depth,
                current_depth=current_depth + 1,
            )
        out.append(value)
    return out


@dataclass
class UserOptions:
    # --size
    output_size: int
    composites_size_low: int
    composites_size_high: int
    # --object
    # --array
    output_is_jobject_else_array: bool  # True means generate json objects, otherwise generate arrays
    # --word-file
    path_to_word_file: Path
    # --word-sample-size
    word_sample_size: int
    # --nested-chance
    # --flat is this thing but 0.0
    nested_chance: float
    # --nested-max-depth
    nested_max_depth: int
    # --pretty
    pretty: bool
    # --seed
    seed: int
    # --nullable <float> <= 1 (negative to never be null)
    nullable_chance: float


def _parse_args(args) -> UserOptions:
    parser = argparse.ArgumentParser(description="json-roulette: a barebones json generator, for testing")
    parser.add_argument("--size", type=int, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--objects", default=False, action="store_true")
    group.add_argument("--arrays", default=False, action="store_true")
    parser.add_argument("--composites-size-low", type=int, required=True)
    parser.add_argument("--composites-size-high", type=int, required=True)
    # optionals
    parser.add_argument("--word-file", type=str, default=None, required=False)
    parser.add_argument("--word-sample-size", type=int, default=50, required=False)
    nested_flags_group = parser.add_mutually_exclusive_group(required=False)
    nested_flags_group.add_argument("--flat", default=False, action="store_true", required=False)
    nested_flags_group.add_argument("--nested-chance", type=float, default=0.2, required=False)
    parser.add_argument("--nested-max-depth", type=int, default=sys.getrecursionlimit() // 2, required=False)
    parser.add_argument("--pretty", default=False, action="store_true", required=False)
    parser.add_argument("--seed", default=time.time(), required=False)
    parser.add_argument("--nullable-chance", type=float, default=0.05, required=False)
    options = parser.parse_args(args)
    local_words = "resources/words"
    tempfile = "/tmp/tempfile_words"
    local_words_exists = Path(local_words).exists()
    if local_words_exists:
        tempfile = local_words
    if not options.word_file and not local_words_exists:
        import urllib.request
        with open(tempfile, "wb") as word_file:
            word_file.write(
                urllib.request.urlopen(
                    "https://raw.githubusercontent.com/gerelef/json-roulette/master/resources/words"
                ).read()
            )
    assert 1 <= options.size
    assert 1 <= options.composites_size_low <= options.composites_size_high
    assert 1 <= options.word_sample_size
    assert 0.0 <= options.nested_chance <= 1.0
    assert 1 <= options.nested_max_depth
    return UserOptions(
        output_is_jobject_else_array=options.objects,
        output_size=options.size,
        composites_size_low=options.composites_size_low,
        composites_size_high=options.composites_size_high,
        path_to_word_file=Path(options.word_file if options.word_file else tempfile).expanduser().absolute(),
        word_sample_size=options.word_sample_size,
        nested_chance=-1 if options.flat else options.nested_chance,
        nested_max_depth=1 if options.flat else options.nested_max_depth,
        pretty=options.pretty,
        seed=options.seed,
        nullable_chance=options.nullable_chance
    )


words = []
if __name__ == "__main__":
    options = _parse_args(sys.argv[1:])
    with open(options.path_to_word_file, "r") as dictionary:
        for line in dictionary:
            words.append(line.strip())
        words = tuple(sorted(random.choices(words, k=options.word_sample_size)))

    random.seed(options.seed)
    primitive_generator = functools.partial(
        generate_random_jfield,
        generate_random_string,
        generate_random_int,
        generate_random_double,
        generate_random_bool,
        nullability_chance=options.nullable_chance
    )
    composite_generator = functools.partial(
        generate_random_jfield,
        generate_jobj,
        generate_jarr,
        nullability_chance=options.nullable_chance
    )
    for i in range(options.output_size):
        generated = generate_jobj(
            primitive_generator,
            composite_generator,
            length_low=options.composites_size_low,
            length_high=options.composites_size_high,
            nested_chance=options.nested_chance,
            nested_max_depth=options.nested_max_depth,
            current_depth=1,
            nullability_chance=-1
        ) if options.output_is_jobject_else_array else generate_jarr(
            primitive_generator,
            composite_generator,
            length_low=options.composites_size_low,
            length_high=options.composites_size_high,
            nested_chance=options.nested_chance,
            nested_max_depth=options.nested_max_depth,
            current_depth=1,
            nullability_chance=-1
        )
        print(json.dumps(generated, indent=4 if options.pretty else None))

    if options.path_to_word_file.name == "tempfile_words":
        os.remove(options.path_to_word_file)
