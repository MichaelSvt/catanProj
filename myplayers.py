import random
import torch
import torch.nn as nn
from catanatron.state_functions import (
    player_key,
)
from catanatron.models.player import Player
from catanatron.game import Game
from catanatron import Player
from catanatron_experimental.cli.cli_players import register_player

from catanatron_experimental.machine_learning.players.tree_search_utils import (
    expand_spectrum,
    list_prunned_actions,
)

from catanatron_experimental.machine_learning.players.value import (
    DEFAULT_WEIGHTS,
    get_value_fn,
)

from catanatron_gym.features import (
    build_production_features,
    reachability_features,
    resource_hand_features,
)


import math
import time
from collections import defaultdict

import numpy as np

from catanatron.game import Game
from catanatron.models.player import Player
from catanatron_experimental.machine_learning.players.playouts import run_playout
from catanatron_experimental.machine_learning.players.tree_search_utils import (
    execute_spectrum,
    list_prunned_actions,
)

from catanatron_experimental.cli.cli_players import register_player

import gymnasium as gym
from gymnasium import spaces
import numpy as np

#   vvv   Michael's imports for reward function   vvv
from collections import defaultdict
from typing import Any, List, Tuple, Dict, Iterable

from catanatron.models.map import BASE_MAP_TEMPLATE, CatanMap
from catanatron.models.board import Board
from catanatron.models.enums import (
    DEVELOPMENT_CARDS,
    MONOPOLY,
    RESOURCES,
    YEAR_OF_PLENTY,
    SETTLEMENT,
    CITY,
    Action,
    ActionPrompt,
    ActionType,
)
from catanatron.models.decks import (
    CITY_COST_FREQDECK,
    DEVELOPMENT_CARD_COST_FREQDECK,
    SETTLEMENT_COST_FREQDECK,
    draw_from_listdeck,
    freqdeck_add,
    freqdeck_can_draw,
    freqdeck_contains,
    freqdeck_draw,
    freqdeck_from_listdeck,
    freqdeck_replenish,
    freqdeck_subtract,
    starting_devcard_bank,
    starting_resource_bank,
)
from catanatron.models.actions import (
    generate_playable_actions,
    road_building_possibilities,
    settlement_possibilities,
    city_possibilities
)
from catanatron.state import resource
from catanatron.state_functions import (
    get_player_buildings,
    build_city,
    build_road,
    build_settlement,
    buy_dev_card,
    maintain_longest_road,
    play_dev_card,
    player_can_afford_dev_card,
    player_can_play_dev,
    player_clean_turn,
    player_freqdeck_add,
    player_deck_draw,
    player_deck_random_draw,
    player_deck_replenish,
    player_freqdeck_subtract,
    player_deck_to_array,
    player_key,
    player_num_resource_cards,
    player_resource_freqdeck_contains,
)

from catanatron.models.player import Color, Player
from catanatron.models.enums import FastResource
#   ^^^   Michael's imports for reward function   ^^^

from catanatron.game import Game, TURNS_LIMIT
from catanatron.models.player import Color, Player, RandomPlayer
from catanatron.players.weighted_random import WeightedRandomPlayer
from catanatron.models.map import BASE_MAP_TEMPLATE, NUM_NODES, LandTile, build_map
from catanatron.models.enums import RESOURCES, Action, ActionType
from catanatron.models.board import get_edges, Board
from catanatron.state_functions import player_key, player_has_rolled
from catanatron_gym.features import (
    create_sample,
    get_feature_ordering,
)
from catanatron_gym.board_tensor_features import (
    create_board_tensor,
    get_channels,
    is_graph_feature,
)


def initial_stage_reward(game, p0_color):
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, p1_color)

    production_reward = calc_init_production_val(game.state, p0_color)
    production_reward -= calc_init_production_val(game.state, p1_color)

    resource_reward = calc_resource_reward(game.state, p_key, p0_color)
    resource_reward -= calc_resource_reward(game.state, p1_key, p1_color)

    return production_reward + resource_reward

def calc_init_production_val(state, p0_color):
    # # the probabilities for 6, 8 are not 5 because they have a higher chance to get blocked
    # prob_dict = {2: 1, 3: 2, 4: 2.8, 5: 3.6, 6: 4.4, 7: 0, 8: 4.4, 9: 3.6, 10: 2.8, 11: 2, 12: 1}
    # p0_total_payout = [0, 0, 0, 0, 0]
    # for number, prob in prob_dict.items():
    #     payout = calculate_resource_production_for_number(state.board, number)
    #     if p0_color in payout.keys():
    #         p0_payout = payout[p0_color]
    #     else:
    #         p0_payout = [0, 0, 0, 0, 0]
    #     for i, amount in enumerate(p0_payout):
    #         if amount == 0:
    #             continue
    #         p0_total_payout[i] += (amount * prob)
    #         p0_total_payout[i] += 0.1 # reward diversity in numbers
    #
    # production_value = 0
    # for p_val in p0_total_payout:
    #     if p_val <= 0:
    #         production_value -= 3.5   # penalty for lack of resource diversity
    #     else:
    #         production_value += p_val
    # return production_value
    # the probabilities for 6, 8 are not 5 because they have a higher chance to get blocked
    prob_dict = {2: 1, 3: 1.95, 4: 2.85, 5: 3.7, 6: 4.5, 7: 0, 8: 4.5, 9: 3.7, 10: 2.85, 11: 1.95, 12: 1}
    p0_total_payout = [0, 0, 0, 0, 0]
    for number, prob in prob_dict.items():
        payout = calculate_resource_production_for_number(state.board, number)
        if p0_color in payout.keys():
            p0_payout = payout[p0_color]
        else:
            p0_payout = [0, 0, 0, 0, 0]
        for i, amount in enumerate(p0_payout):
            if amount == 0:
                continue
            p0_total_payout[i] += (amount * prob)
            if i == 1:
                p0_total_payout[i] += 0.18

    production_value = 0
    for p_val in p0_total_payout:
        if p_val <= 0:
            production_value -= 3.6  # penalty for lack of resource diversity
        else:
            production_value += p_val
    return production_value

def calc_clean_prod(state, p_color):
    prob_dict = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 0, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
    p0_total_payout = [0, 0, 0, 0, 0]
    p0_nodes = [list(), list(), list(), list(), list()]
    for number, prob in prob_dict.items():
        payout = calculate_resource_production_for_number(state.board, number)
        if p_color in payout.keys():
            p0_payout = payout[p_color]
        else:
            p0_payout = [0, 0, 0, 0, 0]

        for i, amount in enumerate(p0_payout):
            for j in range(int(amount)):
                p0_nodes[i].append(number)
            # p0_total_payout[i] += (amount * prob)
    return p0_nodes

def initial_stage_reward2(game, p0_color):
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, p1_color)

    production_reward = calc_init_production_val2(game.state, p0_color)
    production_reward -= calc_init_production_val2(game.state, p1_color)

    resource_reward = calc_resource_reward(game.state, p_key, p0_color)
    resource_reward -= calc_resource_reward(game.state, p1_key, p1_color)

    return production_reward + resource_reward

def calc_init_production_val2(state, p0_color):
    prob_dict = {2: 1, 3: 1.95, 4: 2.85, 5: 3.7, 6: 4.5, 7: 0, 8: 4.5, 9: 3.7, 10: 2.85, 11: 1.95, 12: 1}
    p0_total_payout = [0, 0, 0, 0, 0]
    for number, prob in prob_dict.items():
        payout = calculate_resource_production_for_number(state.board, number)
        if p0_color in payout.keys():
            p0_payout = payout[p0_color]
        else:
            p0_payout = [0, 0, 0, 0, 0]
        for i, amount in enumerate(p0_payout):
            if amount == 0:
                continue
            p0_total_payout[i] += (amount * prob)

    production_value = 0
    for p_val in p0_total_payout:
        if p_val <= 0:
            production_value -= 3.6   # penalty for lack of resource diversity
        else:
            production_value += p_val
    return production_value

def end_stage_reward(game, p0_color):
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, Color.RED)
    total_reward = 0


    winning_reward = get_winning_reward(game, p0_color)
    if winning_reward != 0:
        return winning_reward
    settlement_reward = 5 - game.state.player_state[f"{p_key}_SETTLEMENTS_AVAILABLE"]
    settlement_reward -= (5 - game.state.player_state[f"{p1_key}_SETTLEMENTS_AVAILABLE"])
    settlement_reward *= 50

    city_reward = 4 - game.state.player_state[f"{p_key}_CITIES_AVAILABLE"]
    city_reward -= (4 - game.state.player_state[f"{p1_key}_CITIES_AVAILABLE"])
    city_reward *= 100

    road_reward = game.state.player_state[f"{p_key}_LONGEST_ROAD_LENGTH"]
    road_reward -= game.state.player_state[f"{p1_key}_LONGEST_ROAD_LENGTH"]
    if road_reward < 2 and road_reward > -2:
        road_reward *= 2
    if game.state.player_state[f"{p_key}_HAS_ROAD"]:
        road_reward += 45
    elif game.state.player_state[f"{p1_key}_HAS_ROAD"]:
        road_reward -= 45

    largest_army_reward = game.state.player_state[f"{p_key}_PLAYED_KNIGHT"]
    largest_army_reward -= game.state.player_state[f"{p1_key}_PLAYED_KNIGHT"]
    if largest_army_reward < 2 and largest_army_reward > -2:
        largest_army_reward *= 2
    if game.state.player_state[f"{p_key}_HAS_ARMY"]:
        largest_army_reward += 45
    elif game.state.player_state[f"{p1_key}_HAS_ARMY"]:
        road_reward -= 45

    # development_card_reward = endgame_development_card_reward(game.state, p_key)
    # # print(f"endgame development_card_reward : {development_card_reward}")
    #
    # resource_reward = endgame_resource_reward(game.state, p_key, p0_color)
    # # print(f"endgame resource_reward : {resource_reward}")

    # total_reward += vp_reward
    total_reward += winning_reward
    total_reward += settlement_reward
    total_reward += city_reward
    total_reward += road_reward
    total_reward += largest_army_reward
    # total_reward += development_card_reward
    # total_reward += resource_reward
    # print(f"end game reward = {(total_reward-400)/10}")
    # return (total_reward-400)/10
    return total_reward

# michael's attempt to create a good reward function for PPO agent
def simple_reward2(game, p0_color):
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, p1_color)

    if game.state.player_state[f"{p_key}_ACTUAL_VICTORY_POINTS"] < 2:
        return initial_stage_reward2(game, p0_color)

    winning_reward = get_winning_reward(game, p0_color)
    if winning_reward != 0:
        return winning_reward

    total_reward = 0
    production_reward = 0
    production_reward += calculate_resource_production_value_for_player(game.state, p0_color)
    production_reward -= calculate_resource_production_value_for_player(game.state, p1_color)

    settlement_reward = 1.6 * (5 - game.state.player_state[f"{p_key}_SETTLEMENTS_AVAILABLE"])
    settlement_reward -= 1.6 * (5 - game.state.player_state[f"{p1_key}_SETTLEMENTS_AVAILABLE"])

    city_reward = 3 * (4 - game.state.player_state[f"{p_key}_CITIES_AVAILABLE"])
    city_reward -= 3 * (4 - game.state.player_state[f"{p1_key}_CITIES_AVAILABLE"])

    road_reward = 0.3 * game.state.player_state[f"{p_key}_LONGEST_ROAD_LENGTH"]
    road_reward -= 0.3 * game.state.player_state[f"{p1_key}_LONGEST_ROAD_LENGTH"]
    if game.state.player_state[f"{p_key}_HAS_ROAD"]:
        road_reward += 3
    elif game.state.player_state[f"{p1_key}_HAS_ROAD"]:
        road_reward -= 3

    development_card_reward = calc_development_card_reward(game.state, p_key)

    resource_reward = calc_resource_reward(game.state, p_key, p0_color)
    resource_reward -= calc_resource_reward(game.state, p1_key, p1_color)

    total_reward += production_reward
    total_reward += settlement_reward
    total_reward += city_reward
    total_reward += road_reward
    total_reward += development_card_reward
    total_reward += resource_reward
    return total_reward

# michael's attempt to create a good reward function for PPO agent
def simple_reward(game, p0_color):
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, p1_color)

    if game.state.player_state[f"{p_key}_ACTUAL_VICTORY_POINTS"] < 3:
        return initial_stage_reward(game, p0_color)

    # num_nodes = (5 - game.state.player_state[f"{p_key}_SETTLEMENTS_AVAILABLE"])
    # num_nodes += 2 * (4 - game.state.player_state[f"{p_key}_CITIES_AVAILABLE"])
    # if num_nodes > 6:
    #     return end_stage_reward(game, p0_color)

    winning_reward = get_winning_reward(game, p0_color)
    if winning_reward != 0:
        return winning_reward

    # return 0
    total_reward = 0
    production_reward = 0
    production_reward += calculate_resource_production_value_for_player(game.state, p0_color)
    production_reward -= calculate_resource_production_value_for_player(game.state, p1_color)

    settlement_reward = 2 * (5 - game.state.player_state[f"{p_key}_SETTLEMENTS_AVAILABLE"])
    settlement_reward -= 2 * (5 - game.state.player_state[f"{p1_key}_SETTLEMENTS_AVAILABLE"])

    city_reward = 3 * (4 - game.state.player_state[f"{p_key}_CITIES_AVAILABLE"])
    city_reward -= 3 * (4 - game.state.player_state[f"{p1_key}_CITIES_AVAILABLE"])

    road_reward = 0.3 * game.state.player_state[f"{p_key}_LONGEST_ROAD_LENGTH"]
    road_reward -= 0.3 * game.state.player_state[f"{p1_key}_LONGEST_ROAD_LENGTH"]
    if game.state.player_state[f"{p_key}_HAS_ROAD"]:
        road_reward += 3
    elif game.state.player_state[f"{p1_key}_HAS_ROAD"]:
        road_reward -= 3

    # largest_army_reward = 0.3 * game.state.player_state[f"{p_key}_PLAYED_KNIGHT"]
    # largest_army_reward -= 0.3 * game.state.player_state[f"{p1_key}_PLAYED_KNIGHT"]
    # if game.state.player_state[f"{p_key}_HAS_ARMY"]:
    #     largest_army_reward += 2
    # elif game.state.player_state[f"{p1_key}_HAS_ARMY"]:
    #     road_reward -= 2
    # largest_army_reward *= 0.5

    development_card_reward = calc_development_card_reward(game.state, p_key)
    # development_card_reward -= calc_development_card_reward(game.state, p1_key)
    # development_card_reward *= 0.2
    # # print(f"midgame development_card_reward : {development_card_reward}")

    resource_reward = calc_resource_reward(game.state, p_key, p0_color)
    resource_reward -= calc_resource_reward(game.state, p1_key, p1_color)
    # print(f"midgame resource_reward : {resource_reward}")

    # reachability_sample = reachability_features(game, p0_color, 2)
    # features = [f"P0_0_ROAD_REACHABLE_{resource}" for resource in RESOURCES]
    # reachable_production_at_zero = sum([reachability_sample[f] for f in features])
    # features = [f"P0_1_ROAD_REACHABLE_{resource}" for resource in RESOURCES]
    # reachable_production_at_one = sum([reachability_sample[f] for f in features])
    #
    # enemy_reachability_sample = reachability_features(game, p1_color, 2)
    # features = [f"P0_0_ROAD_REACHABLE_{resource}" for resource in RESOURCES]
    # enemy_reachable_production_at_zero = sum([enemy_reachability_sample[f] for f in features])
    # features = [f"P0_1_ROAD_REACHABLE_{resource}" for resource in RESOURCES]
    # enemy_reachable_production_at_one = sum([enemy_reachability_sample[f] for f in features])


    # reachability_reward = 2*reachable_production_at_zero
    # reachability_reward -= 2 * enemy_reachable_production_at_zero
    # reachability_reward += reachable_production_at_one
    # reachability_reward -= enemy_reachable_production_at_zero

    # print(f"reachable_production_at_zero : {reachable_production_at_zero}")
    # print(f"reachable_production_at_one : {reachable_production_at_one}")
    total_reward += production_reward
    total_reward += settlement_reward
    total_reward += city_reward
    total_reward += road_reward
    # total_reward += largest_army_reward
    total_reward += development_card_reward
    total_reward += resource_reward
    # total_reward += reachability_reward
    # print(f"total_reward : {total_reward}")
    return total_reward

def get_winning_reward(game, p0_color):
    winning_color = game.winning_color()
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    if p0_color == winning_color:
        return 1000
    elif winning_color is None:
        return 0
    else:
        return -1000

def can_build_settlement(state, color):
    key = player_key(state, color)

    if state.player_state[f"{key}_SETTLEMENTS_AVAILABLE"] > 0:
        buildable_node_ids = state.board.buildable_node_ids(color)
        return len(buildable_node_ids)
    else:
        return 0

def has_settlement_to_upgrade(state, color):
    key = player_key(state, color)

    has_cities_available = state.player_state[f"{key}_CITIES_AVAILABLE"] > 0
    if not has_cities_available:
        return 0

    return len(get_player_buildings(state, color, SETTLEMENT))

def calc_development_card_reward(state, p_key):
    dev_card_reward = 0
    # dev_card_reward += 0.15 * state.player_state[f"{p_key}_KNIGHT_IN_HAND"]
    # dev_card_reward += 0.2 * state.player_state[f"{p_key}_YEAR_OF_PLENTY_IN_HAND"]
    # dev_card_reward += 0.25 * state.player_state[f"{p_key}_ROAD_BUILDING_IN_HAND"]
    # dev_card_reward += 0.3 * state.player_state[f"{p_key}_MONOPOLY_IN_HAND"]
    # dev_card_reward += 0.3 * state.player_state[f"{p_key}_VICTORY_POINT_IN_HAND"]

    dev_card_reward -= 0.1 * state.player_state[f"{p_key}_KNIGHT_IN_HAND"]
    dev_card_reward -= 0.1 * state.player_state[f"{p_key}_YEAR_OF_PLENTY_IN_HAND"]
    dev_card_reward -= 0.1 * state.player_state[f"{p_key}_ROAD_BUILDING_IN_HAND"]
    dev_card_reward -= 0.1 * state.player_state[f"{p_key}_MONOPOLY_IN_HAND"]
    dev_card_reward -= 0.1 * state.player_state[f"{p_key}_VICTORY_POINT_IN_HAND"]

    return dev_card_reward

def endgame_development_card_reward(state, p_key):
    dev_card_reward = 0
    dev_card_reward += 1 * state.player_state[f"{p_key}_KNIGHT_IN_HAND"]
    dev_card_reward += 2 * state.player_state[f"{p_key}_YEAR_OF_PLENTY_IN_HAND"]
    dev_card_reward += 3 * state.player_state[f"{p_key}_ROAD_BUILDING_IN_HAND"]
    dev_card_reward += 4 * state.player_state[f"{p_key}_MONOPOLY_IN_HAND"]
    dev_card_reward += 15 * state.player_state[f"{p_key}_VICTORY_POINT_IN_HAND"]
    # dev_card_reward += 2 * state.player_state[f"{p_key}_PLAYED_KNIGHT"]
    # dev_card_reward += 4 *  state.player_state[f"{p_key}_PLAYED_MONOPOLY"]
    # dev_card_reward += 8 *  state.player_state[f"{p_key}_PLAYED_ROAD_BUILDING"]
    # dev_card_reward += 8 *  state.player_state[f"{p_key}_PLAYED_YEAR_OF_PLENTY"]
    return dev_card_reward


def calc_resource_reward(state, p_key, color):
    resource_reward = 0
    resources = {"WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"}

    total_cards_in_hand = 0
    for r in resources:
        total_cards_in_hand += 0.1 * state.player_state[f"{p_key}_{r}_IN_HAND"]

    settlement_locations = can_build_settlement(state, color)
    if settlement_locations > 0:
        resource_reward += 0.45       # we want to have locations to build so we reward
        resource_reward += 0.05*settlement_locations
        miss_for_set = calc_missing_resources_for_settlement(state, p_key)
        if miss_for_set == 0:
            resource_reward += 0.3
        elif miss_for_set == 1:
            resource_reward += 0.2

    if has_settlement_to_upgrade(state, color) > 0:
        miss_for_city = calc_missing_resources_for_city(state, p_key)
        if miss_for_city == 0:
            resource_reward += 1
        elif miss_for_city == 1:
            resource_reward += 0.8
        elif miss_for_city == 2:
            resource_reward += 0.6
        elif miss_for_city == 3:
            resource_reward += 0.2

    if total_cards_in_hand > 7:
        resource_reward -= 0.1
    return resource_reward


def endgame_resource_reward(state, p_key, color):
    resource_reward = 0
    resources = {"WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"}
    total_cards_in_hand = 0
    wood_in_hand = state.player_state[f"{p_key}_WOOD_IN_HAND"]
    total_cards_in_hand += wood_in_hand
    resource_reward += wood_in_hand

    brick_in_hand = state.player_state[f"{p_key}_BRICK_IN_HAND"]
    total_cards_in_hand += brick_in_hand
    resource_reward += brick_in_hand

    sheep_in_hand = state.player_state[f"{p_key}_SHEEP_IN_HAND"]
    total_cards_in_hand += sheep_in_hand
    resource_reward += sheep_in_hand

    wheat_in_hand = state.player_state[f"{p_key}_WHEAT_IN_HAND"]
    total_cards_in_hand += wheat_in_hand
    if wheat_in_hand == 1:
        resource_reward += 3
    elif wheat_in_hand == 2:
        resource_reward += 6
    elif wheat_in_hand > 2:
        resource_reward += 6
        resource_reward += wheat_in_hand - 2

    ore_in_hand = state.player_state[f"{p_key}_ORE_IN_HAND"]
    total_cards_in_hand += ore_in_hand
    if ore_in_hand == 1:
        resource_reward += 3
    elif ore_in_hand == 2:
        resource_reward += 6
    elif ore_in_hand == 3:
        resource_reward += 9
    elif ore_in_hand > 3:
        resource_reward += 9
        resource_reward += ore_in_hand - 2

    settlement_locations = can_build_settlement(state, color)
    if settlement_locations > 0:
        resource_reward += 15       # we want to have locations to build so we reward
        resource_reward += 5*settlement_locations
        miss_for_set = calc_missing_resources_for_settlement(state, p_key)
        if miss_for_set == 0:
            resource_reward += 15
        elif miss_for_set == 1:
            resource_reward += 10

    if has_settlement_to_upgrade(state, color) > 0:
        miss_for_city = calc_missing_resources_for_city(state, p_key)
        if miss_for_city == 0:
            resource_reward += 25
        elif miss_for_city == 1:
            resource_reward += 15

    if total_cards_in_hand > 7:
        resource_reward -= 3

    return (resource_reward / 4) - 5

def calc_missing_resources_for_settlement(state, p_key):
    missing_cards = 4
    if state.player_state[f"{p_key}_WOOD_IN_HAND"] > 0 :
        missing_cards -= 1
    if state.player_state[f"{p_key}_BRICK_IN_HAND"] > 0 :
        missing_cards -= 1
    if state.player_state[f"{p_key}_SHEEP_IN_HAND"] > 0 :
        missing_cards -= 1
    if state.player_state[f"{p_key}_WHEAT_IN_HAND"] > 0 :
        missing_cards -= 1

    return missing_cards

def calc_missing_resources_for_city(state, p_key):
    missing_cards = 5
    ore_in_hand = state.player_state[f"{p_key}_ORE_IN_HAND"]
    if ore_in_hand > 2:
        missing_cards -= 3
    else:
        missing_cards -= ore_in_hand

    wheat_in_hand = state.player_state[f"{p_key}_WHEAT_IN_HAND"]
    if wheat_in_hand > 1:
        missing_cards -= 2
    else:
        missing_cards -= wheat_in_hand

    return missing_cards


def calculate_resource_production_for_number(board, number):
    """Computes resource payouts for given board and dice roll number.

    Args:
        board (Board): Board state
        resource_freqdeck (List[int]): Bank's resource freqdeck
        number (int): Sum of dice roll

    Returns:
        (dict, List[int]): 2-tuple.
            First element is color => freqdeck mapping. e.g. {Color.RED: [0,0,0,3,0]}.
            Second is an array of resources that couldn't be yieleded
            because they depleted.
    """

    intented_payout: Dict[Color, Dict[FastResource, int]] = defaultdict(
        lambda: defaultdict(int))
    for coordinate, tile in board.map.land_tiles.items():
        if tile.number != number:
            continue  # doesn't yield

        robber_penalty = 1
        if board.robber_coordinate == coordinate:
            robber_penalty = 0.9

        for node_id in tile.nodes.values():
            building = board.buildings.get(node_id, None)
            assert tile.resource is not None
            gain = 0
            if building is None:
                continue
            elif building[1] == SETTLEMENT:
                gain = 1
            elif building[1] == CITY:
                gain = 2
            intented_payout[building[0]][tile.resource] += (gain*robber_penalty)

    # build final data color => freqdeck structure
    payout = {}
    for player, player_payout in intented_payout.items():
        payout[player] = [0, 0, 0, 0, 0]

        for resource, count in player_payout.items():
            freqdeck_replenish(payout[player], count, resource)

    return payout

def calculate_resource_production_value_for_player(state, p0_color):
    # the probabilities for 6, 8 are not 5 because they have a higher chance to get blocked
    prob_dict = {2: 1, 3: 1.95, 4: 2.85, 5: 3.7, 6: 4.5, 7: 0, 8: 4.5, 9: 3.7, 10: 2.85, 11: 1.95, 12: 1}
    p0_total_payout = [0, 0, 0, 0, 0]
    for number, prob in prob_dict.items():
        payout = calculate_resource_production_for_number(state.board, number)

        if p0_color in payout.keys():
            p0_payout = payout[p0_color]
        else:
            p0_payout = [0, 0, 0, 0, 0]
        for i, amount in enumerate(p0_payout):
            if amount == 0:
                continue
            # p0_total_payout[i] += (((amount+1)/2) * prob)  # 4/36 prob to get 1 is better than 2/36 to get 2
            p0_total_payout[i] += (amount * prob)
            if i==4:    #ore
                p0_total_payout[i] += 0.1

    production_value = 0

    for p_val in p0_total_payout:
        if p_val <= 0:
            production_value -= 3   # penalty for lack of resource diversity
        else:
            production_value += p_val
    return production_value


@register_player("MYVF")
class MyVFPlayer(Player):
    """
    Player that chooses actions by maximizing Victory Points greedily.
    If multiple actions lead to the same max-points-achievable
    in this turn, selects from them at random.
    """

    def decide(self, game: Game, playable_actions):
        if len(playable_actions) == 1:
            return playable_actions[0]

        best_value = float("-inf")
        best_actions = []
        for action in playable_actions:
            game_copy = game.copy()
            game_copy.execute(action)

            # key = player_key(game_copy.state, self.color)

            value = simple_reward(game_copy, self.color)
            if value == best_value:
                best_actions.append(action)
            if value > best_value:
                best_value = value
                best_actions = [action]

        chosen_action = random.choice(best_actions)
        # early_game_turns = range(2,5)
        # p1_color = Color.RED
        # if self.color == p1_color:
        #     p1_color = Color.BLUE
        #
        # p_key = player_key(game.state, self.color)
        # p1_key = player_key(game.state, p1_color)
        # p0_vp_0 = game.state.player_state[f"{p_key}_ACTUAL_VICTORY_POINTS"]

        # if game.state.num_turns in early_game_turns:
        # if p0_vp_0 == 2 and game.state.num_turns < 6:
        #     game_copy = game.copy()
        #     game_copy.execute(chosen_action)
        #     p0_prod = calc_clean_prod(game_copy.state, self.color)
        #     p1_prod = calc_clean_prod(game_copy.state, p1_color)
        #     p0_prod_val = calc_init_production_val(game_copy.state, self.color)
        #     p1_prod_val = calc_init_production_val(game_copy.state, p1_color)
            # print(f"num turns:{game.state.num_turns},{self.color} production:\t{p0_prod}\t,val:{p0_prod_val:.2f}")
            # print(f"num turns:{game.state.num_turns},{p1_color} production:\t{p1_prod}\t,val:{p1_prod_val:.2f}")

        # elif game.state.num_turns-40 in early_game_turns or  game.state.num_turns-50 in early_game_turns:
        #     game_copy = game.copy()
        #     game_copy.execute(chosen_action)
        #     st = game_copy.state
        #     p0_p = calc_clean_prod(game_copy.state, self.color)
        #     p1_p = calc_clean_prod(game_copy.state, p1_color)
        #     p0_pv = calculate_resource_production_value_for_player(st, self.color)
        #     p1_pv = calculate_resource_production_value_for_player(st, p1_color)
        #     p0_vp = st.player_state[f"{p_key}_ACTUAL_VICTORY_POINTS"]
        #     p1_vp = st.player_state[f"{p1_key}_ACTUAL_VICTORY_POINTS"]
            # print(f"turns:{st.num_turns},{self.color}\tvp:{p0_vp}\tprod:\t{p0_p}\t,val:{p0_pv:.2f}")
            # print(f"turns:{st.num_turns},{p1_color}\tvp:{p1_vp}\tprod:\t{p1_p}\t,val:{p1_pv:.2f}")


        return chosen_action





def calc_clean_prod(state, p_color):
    prob_dict = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 0, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
    p0_total_payout = [0, 0, 0, 0, 0]
    # p0_nodes = [list(), list(), list(), list(), list()]
    for number, prob in prob_dict.items():
        payout = calculate_resource_production_for_number(state.board, number)
        if p_color in payout.keys():
            p0_payout = payout[p_color]
        else:
            p0_payout = [0, 0, 0, 0, 0]

        for i, amount in enumerate(p0_payout):
            # for j in range(int(amount)):
            #     p0_nodes[i].append(number)
            p0_total_payout[i] += (amount * prob)
    return p0_total_payout

def calc_dev_card_in_hand(state, p_key):
    dev_card_in_hand = 0
    dev_card_in_hand += state.player_state[f"{p_key}_KNIGHT_IN_HAND"]
    dev_card_in_hand += state.player_state[f"{p_key}_YEAR_OF_PLENTY_IN_HAND"]
    dev_card_in_hand += state.player_state[f"{p_key}_ROAD_BUILDING_IN_HAND"]
    dev_card_in_hand += state.player_state[f"{p_key}_MONOPOLY_IN_HAND"]
    dev_card_in_hand += state.player_state[f"{p_key}_VICTORY_POINT_IN_HAND"]

    return dev_card_in_hand

def generate_x(game, p0_color):
    p1_color = Color.RED
    if p0_color == p1_color:
        p1_color = Color.BLUE
    p_key = player_key(game.state, p0_color)
    p1_key = player_key(game.state, p1_color)

    state = game.state
    board = state.board
    player_state = state.player_state

    p0_settle = get_player_buildings(state, p0_color, SETTLEMENT)
    p1_settle = get_player_buildings(state, p1_color, SETTLEMENT)
    p0_city = get_player_buildings(state, p0_color, CITY)
    p1_city = get_player_buildings(state, p1_color, CITY)

    X = np.zeros(363)
    for i in range(54):

        if i in p0_settle:
            X[6 * i] = 1
        if i in p1_settle:
            X[6 * i] = -1
        if i in p0_city:
            X[6 * i] = 2
        if i in p1_city:
            X[6 * i] = -2

        for j, resource in enumerate(RESOURCES):
            X[(6 * i) + (j + 1)] = get_node_production(game.state.board.map, i, resource)

    # features for player 0 (BLUE / me)
    X[324] = player_state[f"{p_key}_VICTORY_POINTS"]
    X[325] = player_state[f"{p_key}_SETTLEMENTS_AVAILABLE"]
    X[326] = player_state[f"{p_key}_CITIES_AVAILABLE"]
    X[327] = player_state[f"{p_key}_ROADS_AVAILABLE"] / 13
    X[328] = player_state[f"{p_key}_PLAYED_KNIGHT"]
    X[329] = player_state[f"{p_key}_HAS_ARMY"]
    X[330] = player_state[f"{p_key}_HAS_ROAD"]
    X[331] = player_state[f"{p_key}_LONGEST_ROAD_LENGTH"]
    X[332] = calc_dev_card_in_hand(state, p_key)
    for j, r in enumerate(RESOURCES):
        X[333 + j] = player_state[f"{p_key}_{r}_IN_HAND"]
    p0_prod = calc_clean_prod(game.state, p0_color)
    for j, p in enumerate(p0_prod):
        X[338+j] = p

    # features for player 1 (RED / enemy)
    X[343] = player_state[f"{p1_key}_VICTORY_POINTS"]
    X[344] = player_state[f"{p1_key}_SETTLEMENTS_AVAILABLE"]
    X[345] = player_state[f"{p1_key}_CITIES_AVAILABLE"]
    X[346] = player_state[f"{p1_key}_ROADS_AVAILABLE"] / 13
    X[347] = player_state[f"{p1_key}_PLAYED_KNIGHT"]
    X[348] = player_state[f"{p1_key}_HAS_ARMY"]
    X[349] = player_state[f"{p1_key}_HAS_ROAD"]
    X[350] = player_state[f"{p1_key}_LONGEST_ROAD_LENGTH"]
    X[351] = calc_dev_card_in_hand(state, p1_key)
    for j, r in enumerate(RESOURCES):
        X[352 + j] = player_state[f"{p1_key}_{r}_IN_HAND"]
    p1_prod = calc_clean_prod(game.state, p1_color)
    for j, p in enumerate(p1_prod):
        X[357 + j] = p

    X[362] = state.num_turns

    return X

def get_node_production(catan_map, node_id, resource):

    prob_dict = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 0, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
    production = 0
    for tile in catan_map.adjacent_tiles[node_id]:
        if tile.resource == resource:
            production += prob_dict[tile.number]

    return production

class Net(nn.Module):
    def __init__(self, input_size=363):
        super(Net, self).__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.fc2 = nn.Linear(128, 64)
        self.output = nn.Linear(64, 1)

        # self.fc1 = nn.Linear(input_size, 64)
        # self.fc2 = nn.Linear(64, 32)
        # self.output = nn.Linear(32, 1)

        self.fc1 = nn.Linear(input_size, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 16)
        self.output = nn.Linear(16, 1)

        self.sigmoid = nn.Sigmoid()
        self.dropout = nn.Dropout(0.5)  # Optional dropout for regularization

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        x = self.sigmoid(self.output(x))
        return x


@register_player("NN")
class MyNNPlayer(Player):
    """
    Player that chooses actions by maximizing Victory Points greedily.
    If multiple actions lead to the same max-points-achievable
    in this turn, selects from them at random.
    """

    def __init__(self, color, value_fn_builder_name=None, params=None, is_bot=True, epsilon=None):
        super().__init__(color, is_bot)
        # self.model = torch.load('FvF_66K_363feat_model.pth')
        #
        # # Make sure to call model.eval() if you're in inference mode
        # self.model.eval()
        self.model = Net()

        # Load the state_dict

        # torch.save(model.state_dict(), )
        # self.model.load_state_dict(torch.load('FvF_22VP_114K_363feat_model_weights.pth'))
        # self.model.load_state_dict(torch.load('FvF_turn_20_114K_363feat_model_weights.pth'))


        # self.model.load_state_dict(torch.load(f'FvF_all_129K_363feat_model_weights_epoch39.pth'))

        # NN1
        # self.model.load_state_dict(torch.load(f'363_64_32_16_1_FvF_all_129K_363feat_model_weights_epoch29.pth'))

        # NN2
        # self.model.load_state_dict(torch.load(f'NN2vNN2_47K_b16_lr005_model_weights_epoch19.pth'))

        # NN3
        self.model.load_state_dict(torch.load(f'NN3vNN3_114K_b8_lr0002_model_weights_epoch20.pth'))

        self.model.eval()

    def decide(self, game: Game, playable_actions):
        if len(playable_actions) == 1:
            return playable_actions[0]

        best_value = float("-inf")
        best_actions = []
        for action in playable_actions:
            game_copy = game.copy()
            game_copy.execute(action)

            action_vector = generate_x(game_copy, self.color)

            # key = player_key(game_copy.state, self.color)
            action_value = self.model(torch.tensor(action_vector, dtype=torch.float32))
            if action_value == best_value:
                best_actions.append(action)
            if action_value > best_value:
                best_value = action_value
                best_actions = [action]

        return random.choice(best_actions)


@register_player("NN2")
class MyNN2Player(Player):
    """
    Player that chooses actions by maximizing Victory Points greedily.
    If multiple actions lead to the same max-points-achievable
    in this turn, selects from them at random.
    """

    def __init__(self, color, value_fn_builder_name=None, params=None, is_bot=True, epsilon=None):
        super().__init__(color, is_bot)
        # self.model = torch.load('FvF_66K_363feat_model.pth')
        #
        # # Make sure to call model.eval() if you're in inference mode
        self.model = Net()


    # Load the state_dict

        # torch.save(model.state_dict(), )
        # self.model.load_state_dict(torch.load('FvF_22VP_114K_363feat_model_weights.pth'))
        # self.model.load_state_dict(torch.load('FvF_turn_20_114K_363feat_model_weights.pth'))


        # self.model.load_state_dict(torch.load(f'FvF_all_129K_363feat_model_weights_epoch39.pth'))

        # self.model.load_state_dict(torch.load(f'363_64_32_16_1_FvF_all_129K_363feat_model_weights_epoch29.pth'))

        # NN1
        # self.model.load_state_dict(torch.load(f'363_64_32_16_1_FvF_all_129K_363feat_model_weights_epoch29.pth'))

        # NN2
        self.model.load_state_dict(torch.load(f'NN2vNN2_47K_b16_lr005_model_weights_epoch19.pth'))

        # NN3
        # self.model.load_state_dict(torch.load(f'NN3vNN3_114K_b8_lr0002_model_weights_epoch20.pth'))

        self.model.eval()

    def decide(self, game: Game, playable_actions):
        if len(playable_actions) == 1:
            return playable_actions[0]

        best_value = float("-inf")
        best_actions = []
        for action in playable_actions:
            game_copy = game.copy()
            game_copy.execute(action)

            action_vector = generate_x(game_copy, self.color)

            # key = player_key(game_copy.state, self.color)
            action_value = self.model(torch.tensor(action_vector, dtype=torch.float32))
            if action_value == best_value:
                best_actions.append(action)
            if action_value > best_value:
                best_value = action_value
                best_actions = [action]

        return random.choice(best_actions)


#
#
# ALPHABETA_DEFAULT_DEPTH = 2
# MAX_SEARCH_TIME_SECS = 20
#
# @register_player("MYAB")
# class MyABPlayer(Player):
#     """
#     Player that executes an AlphaBeta Search where the value of each node
#     is taken to be the expected value (using the probability of rolls, etc...)
#     of its children. At leafs we simply use the heuristic function given.
#
#     NOTE: More than 3 levels seems to take much longer, it would be
#     interesting to see this with prunning.
#     """
#
#     def __init__(
#         self,
#         color,
#         depth=ALPHABETA_DEFAULT_DEPTH,
#         prunning=False,
#         value_fn_builder_name=None,
#         params=DEFAULT_WEIGHTS,
#         epsilon=None,
#     ):
#         super().__init__(color)
#         self.depth = int(depth)
#         self.prunning = str(prunning).lower() != "false"
#         self.value_fn_builder_name = (
#             "contender_fn" if value_fn_builder_name == "C" else "base_fn"
#         )
#         self.params = params
#         self.use_value_function = None
#         self.epsilon = epsilon
#
#     def value_function(self, game, p0_color):
#         raise NotImplementedError
#
#     def get_actions(self, game):
#         if self.prunning:
#             return list_prunned_actions(game)
#         return game.state.playable_actions
#
#     def decide(self, game: Game, playable_actions):
#         actions = self.get_actions(game)
#         if len(actions) == 1:
#             return actions[0]
#
#         if self.epsilon is not None and random.random() < self.epsilon:
#             return random.choice(playable_actions)
#
#         start = time.time()
#         state_id = str(len(game.state.actions))
#         node = DebugStateNode(state_id, self.color)  # i think it comes from outside
#         deadline = start + MAX_SEARCH_TIME_SECS
#         result = self.alphabeta(
#             game.copy(), self.depth, float("-inf"), float("inf"), deadline, node
#         )
#         # print("Decision Results:", self.depth, len(actions), time.time() - start)
#         # if game.state.num_turns > 10:
#         #     render_debug_tree(node)
#         #     breakpoint()
#         if result[0] is None:
#             return playable_actions[0]
#         return result[0]
#
#     def __repr__(self) -> str:
#         return (
#             super().__repr__()
#             + f"(depth={self.depth},value_fn={self.value_fn_builder_name},prunning={self.prunning})"
#         )
#
#     def alphabeta(self, game, depth, alpha, beta, deadline, node):
#         """AlphaBeta MiniMax Algorithm.
#
#         NOTE: Sometimes returns a value, sometimes an (action, value). This is
#         because some levels are state=>action, some are action=>state and in
#         action=>state would probably need (action, proba, value) as return type.
#
#         {'value', 'action'|None if leaf, 'node' }
#         """
#         if depth == 0 or game.winning_color() is not None or time.time() >= deadline:
#             value = simple_reward(game, self.color)
#
#             node.expected_value = value
#             return None, value
#
#         maximizingPlayer = game.state.current_color() == self.color
#         actions = self.get_actions(game)  # list of actions.
#         action_outcomes = expand_spectrum(game, actions)  # action => (game, proba)[]
#
#         if maximizingPlayer:
#             best_action = None
#             best_value = float("-inf")
#             for i, (action, outcomes) in enumerate(action_outcomes.items()):
#                 action_node = DebugActionNode(action)
#
#                 expected_value = 0
#                 for j, (outcome, proba) in enumerate(outcomes):
#                     out_node = DebugStateNode(f"{node.label} {i} {j}", outcome.state.current_color())
#
#                     result = self.alphabeta(outcome, depth - 1, alpha, beta, deadline, out_node)
#                     value = result[1]
#                     expected_value += proba * value
#
#                     action_node.children.append(out_node)
#                     action_node.probas.append(proba)
#
#                 action_node.expected_value = expected_value
#                 node.children.append(action_node)
#
#                 if expected_value > best_value:
#                     best_action = action
#                     best_value = expected_value
#                 alpha = max(alpha, best_value)
#                 if alpha >= beta:
#                     break  # beta cutoff
#
#             node.expected_value = best_value
#             return best_action, best_value
#         else:
#             best_action = None
#             best_value = float("inf")
#             for i, (action, outcomes) in enumerate(action_outcomes.items()):
#                 action_node = DebugActionNode(action)
#
#                 expected_value = 0
#                 for j, (outcome, proba) in enumerate(outcomes):
#                     out_node = DebugStateNode(
#                         f"{node.label} {i} {j}", outcome.state.current_color()
#                     )
#
#                     result = self.alphabeta(
#                         outcome, depth - 1, alpha, beta, deadline, out_node
#                     )
#                     value = result[1]
#                     expected_value += proba * value
#
#                     action_node.children.append(out_node)
#                     action_node.probas.append(proba)
#
#                 action_node.expected_value = expected_value
#                 node.children.append(action_node)
#
#                 if expected_value < best_value:
#                     best_action = action
#                     best_value = expected_value
#                 beta = min(beta, best_value)
#                 if beta <= alpha:
#                     break  # alpha cutoff
#
#             node.expected_value = best_value
#             return best_action, best_value
#
#
# class DebugStateNode:
#     def __init__(self, label, color):
#         self.label = label
#         self.children = []  # DebugActionNode[]
#         self.expected_value = None
#         self.color = color
#
#
# class DebugActionNode:
#     def __init__(self, action):
#         self.action = action
#         self.expected_value: Any = None
#         self.children = []  # DebugStateNode[]
#         self.probas = []
#
#
