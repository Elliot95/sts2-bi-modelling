"""
Pure transformation: one parsed .run JSON document -> rows for each raw table.

No GCP dependencies, so the same code is used by the Cloud Function (one run
per GCS upload) and by scripts/backfill_table.py (all history in one batch).
"""

import datetime
import json


def _run_date(start_time: int) -> str:
    return datetime.datetime.fromtimestamp(start_time, datetime.timezone.utc).date().isoformat()


def save_source(object_name: str) -> str:
    """Which save folder a run came from, from its path under raw/ in GCS:
    raw/<file>.run -> Vanilla (the original profile1 uploads),
    raw/modded/profileN/<file>.run -> Modded, raw/profileN/<file>.run -> Profile N."""
    parts = object_name.split("/")[1:-1]
    if "modded" in parts:
        return "Modded"
    profile = next((p for p in parts if p.startswith("profile")), "profile1")
    return "Vanilla" if profile == "profile1" else f"Profile {profile[len('profile'):]}"


def flatten_run(data: dict, source: str = "Vanilla") -> dict[str, list[dict]]:
    run_id = data["start_time"]
    run_date = _run_date(run_id)
    primary_player = (data.get("players") or [{}])[0]

    fact_run = [{
        "run_id": run_id,
        "run_date": run_date,
        "seed": data.get("seed"),
        "build_id": data.get("build_id"),
        "game_mode": data.get("game_mode"),
        "platform_type": data.get("platform_type"),
        "ascension": data.get("ascension"),
        "character": primary_player.get("character"),
        "acts_completed": len(data.get("acts", [])),
        "run_time_seconds": data.get("run_time"),
        "killed_by_encounter": data.get("killed_by_encounter"),
        "killed_by_event": data.get("killed_by_event"),
        "was_abandoned": data.get("was_abandoned"),
        "win": data.get("win"),
        "schema_version": data.get("schema_version"),
        "save_source": source,
    }]

    floor_state, card_choices, cards_gained, event_choices, potion_events = [], [], [], [], []
    rooms, rest_choices = [], []

    floor_number = 0
    for act_index, act in enumerate(data.get("map_point_history", [])):
        for point_index, point in enumerate(act):
            floor_number += 1
            # The event on this floor comes from its room, not from the choice
            # key: for Ancients (Neow, Tezcatara...) the choice is a relic
            # ("GOLDEN_COMPASS.title" in the relics table), not an event option.
            event_id = next((room.get("model_id") for room in (point.get("rooms") or [])
                             if (room.get("model_id") or "").startswith("EVENT.")), None)
            # Rooms are shared by all players on the floor (usually one; an
            # event can lead into a fight, giving two).
            for room_index, room in enumerate(point.get("rooms") or []):
                monsters = room.get("monster_ids") or []
                rooms.append({
                    "run_id": run_id,
                    "run_date": run_date,
                    "floor_number": floor_number,
                    "act_index": act_index,
                    "room_index": room_index,
                    "room_type": room.get("room_type"),
                    "model_id": room.get("model_id"),
                    "monster_ids": "|".join(monsters),
                    "monster_count": len(monsters),
                    "turns_taken": room.get("turns_taken"),
                })
            for stats in point.get("player_stats", []):
                player_id = stats.get("player_id")

                floor_state.append({
                    "run_id": run_id,
                    "run_date": run_date,
                    "act_index": act_index,
                    "map_point_index": point_index,
                    "floor_number": floor_number,
                    "player_id": player_id,
                    "map_point_type": point.get("map_point_type"),
                    "current_hp": stats.get("current_hp"),
                    "max_hp": stats.get("max_hp"),
                    "current_gold": stats.get("current_gold"),
                    "damage_taken": stats.get("damage_taken"),
                    "hp_healed": stats.get("hp_healed"),
                    "gold_gained": stats.get("gold_gained"),
                    "gold_lost": stats.get("gold_lost"),
                    "gold_spent": stats.get("gold_spent"),
                    "gold_stolen": stats.get("gold_stolen"),
                    "max_hp_gained": stats.get("max_hp_gained"),
                    "max_hp_lost": stats.get("max_hp_lost"),
                })

                for choice in stats.get("card_choices", []):
                    card = choice.get("card") or {}
                    card_choices.append({
                        "run_id": run_id,
                        "run_date": run_date,
                        "floor_number": floor_number,
                        "player_id": player_id,
                        "card_id": card.get("id"),
                        "floor_added_to_deck": card.get("floor_added_to_deck"),
                        "was_picked": choice.get("was_picked"),
                    })

                for gained in stats.get("cards_gained", []):
                    cards_gained.append({
                        "run_id": run_id,
                        "run_date": run_date,
                        "floor_number": floor_number,
                        "player_id": player_id,
                        "card_id": gained.get("id"),
                    })

                # Potions: offered (with was_picked), then used / discarded /
                # bought on this floor. One row per potion per action.
                def potion(potion_id, action, was_picked=None):
                    potion_events.append({
                        "run_id": run_id,
                        "run_date": run_date,
                        "floor_number": floor_number,
                        "act_index": act_index,
                        "player_id": player_id,
                        "potion_id": potion_id,
                        "action": action,
                        "was_picked": was_picked,
                    })
                for choice in stats.get("potion_choices") or []:
                    potion(choice.get("choice"), "offered", choice.get("was_picked"))
                for action, key in (("used", "potion_used"), ("discarded", "potion_discarded"),
                                    ("bought", "bought_potions")):
                    for potion_id in stats.get(key) or []:
                        potion(potion_id, action)

                for choice_index, option in enumerate(stats.get("rest_site_choices") or []):
                    rest_choices.append({
                        "run_id": run_id,
                        "run_date": run_date,
                        "floor_number": floor_number,
                        "act_index": act_index,
                        "player_id": player_id,
                        "choice_index": choice_index,
                        "rest_option": option,
                    })

                # Multi-step events record several choices on one floor, in order.
                for choice_index, choice in enumerate(stats.get("event_choices") or []):
                    title = choice.get("title") or {}
                    key = title.get("key") or ""
                    event_choices.append({
                        "run_id": run_id,
                        "run_date": run_date,
                        "floor_number": floor_number,
                        "act_index": act_index,
                        "player_id": player_id,
                        "choice_index": choice_index,
                        # A few choices happen on floors whose room isn't the event
                        # (e.g. the Key Door after a boss); its key still names it.
                        "event_id": event_id or (f"EVENT.{key.split('.')[0]}"
                                                 if title.get("table") == "events" and key else None),
                        "choice_table": title.get("table"),
                        "choice_key": key.removesuffix(".title"),
                        # Rewards/details vary by event (card offered, gold,
                        # enchantment...), so they're kept as JSON for dbt.
                        "variables_json": json.dumps(choice.get("variables") or {}, sort_keys=True),
                    })

    relics, deck_cards, run_potions = [], [], []
    for player in data.get("players", []):
        player_id = player.get("id")
        for relic in player.get("relics", []):
            relics.append({
                "run_id": run_id,
                "run_date": run_date,
                "player_id": player_id,
                "relic_id": relic.get("id"),
                "floor_added_to_deck": relic.get("floor_added_to_deck"),
            })
        # Potions still held when the run ended (for a loss: died holding them).
        for held in player.get("potions") or []:
            run_potions.append({
                "run_id": run_id,
                "run_date": run_date,
                "player_id": player_id,
                "potion_id": held.get("id"),
                "slot_index": held.get("slot_index"),
                "max_potion_slot_count": player.get("max_potion_slot_count"),
            })
        for card in player.get("deck", []):
            deck_cards.append({
                "run_id": run_id,
                "run_date": run_date,
                "player_id": player_id,
                "card_id": card.get("id"),
                "floor_added_to_deck": card.get("floor_added_to_deck"),
            })

    return {
        "fact_run": fact_run,
        "fact_floor_state": floor_state,
        "fact_card_choice": card_choices,
        "fact_cards_gained": cards_gained,
        "fact_relic": relics,
        "fact_deck_card": deck_cards,
        "fact_event_choice": event_choices,
        "fact_potion_event": potion_events,
        "fact_run_potion": run_potions,
        "fact_room": rooms,
        "fact_rest_choice": rest_choices,
    }
