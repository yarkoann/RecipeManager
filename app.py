import streamlit as st
import json
import re
import os
from typing import List, Dict, Optional
from datetime import datetime

from diet_analyzer import (diet_analyzer, analyze_diet_compatibility,
                           DishContextClassifier, AdaptationFeasibilityChecker)


# ─────────────────────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

CAN_GRAMS: Dict[str, int] = {
    "горох": 400, "фасоль": 400, "кукуруза": 340, "нут": 400,
    "чечевица": 400, "томаты": 400, "огурцы": 400, "грибы": 400,
    "оливки": 300, "тунец": 185, "сардины": 185,
}

# Примерная калорийность и БЖУ на 100г (ккал, белки г, жиры г, углеводы г)
NUTRITION_DB: Dict[str, tuple] = {
    "мука": (364, 10, 1, 76), "яйца": (155, 13, 11, 1),
    "молоко": (61, 3.2, 3.2, 5), "сахар": (387, 0, 0, 100),
    "масло сливочное": (748, 0.5, 82, 0.8), "масло растительное": (884, 0, 100, 0),
    "творог": (120, 18, 5, 3), "соль": (0, 0, 0, 0),
    "разрыхлитель": (53, 0, 0, 28), "какао": (289, 20, 14, 11),
    "картофель": (77, 2, 0.1, 17), "морковь": (41, 0.9, 0.2, 10),
    "лук": (40, 1.1, 0.1, 9), "чеснок": (149, 6.4, 0.5, 33),
    "помидор": (20, 0.9, 0.2, 3.9), "огурец": (15, 0.7, 0.1, 2.5),
    "огурцы соленые": (11, 0.8, 0.1, 1.3), "колбаса": (250, 11, 22, 2),
    "майонез": (680, 2.4, 74, 2.6), "горох": (298, 23, 1.6, 49),
    "курица": (165, 31, 4, 0), "мясо": (200, 18, 14, 0),
    "рыба": (140, 20, 6, 0), "тофу": (76, 8, 4, 2),
    "гречка": (313, 12, 3, 62), "рис": (344, 7, 1, 79),
    "овсянка": (389, 17, 7, 66), "макароны": (338, 12, 2, 70),
    "хлеб": (265, 9, 3, 49), "сыр": (400, 25, 33, 0),
    "кефир": (51, 4, 2, 4), "сметана": (206, 3, 20, 4),
    "банан": (89, 1.1, 0.3, 23), "яблоко": (52, 0.3, 0.2, 14),
    "авокадо": (160, 2, 15, 9), "грибы": (22, 3, 0.5, 3),
    "нутовая мука": (387, 22, 6, 58), "миндальная мука": (571, 21, 50, 21),
    "кокосовая мука": (400, 18, 15, 60),
}


def can_to_grams(product_name: str, cans: float) -> float:
    return cans * CAN_GRAMS.get(product_name.lower(), 400)


def load_css():
    css_file = "static/css/style.css"
    if os.path.exists(css_file):
        with open(css_file, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


def calculate_nutrition(ingredients: list) -> dict:
    """Расчёт КБЖУ для адаптированного рецепта."""
    total = {"ккал": 0, "белки": 0, "жиры": 0, "углеводы": 0}
    for ing in ingredients:
        if ing.get('by_taste') or ing.get('quantity') is None:
            continue
        name = ing.get('name', '').lower()
        qty = ing.get('quantity', 0) or 0
        unit = ing.get('unit', '')
        # Переводим всё в граммы
        if unit == 'банка':
            grams = can_to_grams(name, qty)
        elif unit == 'мл':
            grams = qty  # плотность ≈ 1
        elif unit == 'шт':
            grams = qty * 50  # среднее яйцо/штучный продукт
        elif unit in ('ст.л', 'ч.л'):
            grams = qty * (15 if unit == 'ст.л' else 5)
        elif unit == 'кг':
            grams = qty * 1000
        else:
            grams = qty

        if name in NUTRITION_DB:
            kcal, prot, fat, carb = NUTRITION_DB[name]
            factor = grams / 100
            total["ккал"] += kcal * factor
            total["белки"] += prot * factor
            total["жиры"] += fat * factor
            total["углеводы"] += carb * factor

    return {k: round(v, 1) for k, v in total.items()}


# ─────────────────────────────────────────────────────────────────────────────
#  RecipeManager
# ─────────────────────────────────────────────────────────────────────────────

class RecipeManager:
    def __init__(self,
                 recipes_file="data/recipes.json",
                 ingredients_file="data/ingredients.json",
                 substitutions_file="data/substitutions.json"):
        self.recipes_file = recipes_file
        self.ingredients_file = ingredients_file
        self.substitutions_file = substitutions_file
        self.recipes = self._load_json(recipes_file).get("recipes", [])
        self.ingredients = self._load_json(ingredients_file).get("ingredients", [])
        self.substitutions = self._load_json(substitutions_file).get("substitutions", [])

    def _load_json(self, filename):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}

    def _save_json(self, data, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all_recipes(self):
        return self.recipes

    def get_recipe_by_id(self, recipe_id):
        return next((r for r in self.recipes if r.get("id") == recipe_id), None)

    def get_recipes_by_category(self, category):
        return [r for r in self.recipes if r.get("category") == category]

    def search_recipes(self, query):
        query = query.lower()
        return [r for r in self.recipes if query in r["name"].lower()]

    def add_recipe(self, recipe):
        for existing in self.recipes:
            if existing.get('name', '').lower() == recipe.get('name', '').lower():
                return None
        new_id = max([r.get("id", 0) for r in self.recipes] + [0]) + 1
        recipe["id"] = new_id
        self.recipes.append(recipe)
        self._save_json({"recipes": self.recipes}, self.recipes_file)
        return new_id

    def update_recipe(self, recipe_id: int, updated_data: dict) -> bool:
        """Обновляет рецепт по ID."""
        for i, recipe in enumerate(self.recipes):
            if recipe.get("id") == recipe_id:
                updated_data["id"] = recipe_id
                self.recipes[i] = updated_data
                self._save_json({"recipes": self.recipes}, self.recipes_file)
                return True
        return False

    def delete_recipe(self, recipe_id: int) -> bool:
        """Удаляет рецепт по ID."""
        before = len(self.recipes)
        self.recipes = [r for r in self.recipes if r.get("id") != recipe_id]
        if len(self.recipes) < before:
            self._save_json({"recipes": self.recipes}, self.recipes_file)
            return True
        return False

    def search_by_available_ingredients(self, user_products: list) -> list:
        """Умный поиск: находит рецепты, для которых больше всего ингредиентов есть у пользователя."""
        user_names = {p['name'].lower() for p in user_products if p.get('name')}
        results = []
        for recipe in self.recipes:
            required = [
                ing for ing in recipe.get('ingredients', [])
                if not ing.get('by_taste') and ing.get('quantity') is not None
            ]
            if not required:
                continue
            matched = sum(
                1 for ing in required
                if any(u in ing['name'].lower() or ing['name'].lower() in u for u in user_names)
            )
            pct = round(matched / len(required) * 100) if required else 0
            missing_count = len(required) - matched
            results.append({
                'recipe': recipe,
                'matched': matched,
                'total': len(required),
                'pct': pct,
                'missing': missing_count,
            })
        results.sort(key=lambda x: x['pct'], reverse=True)
        return results

    def get_ingredient_info(self, name):
        return next((i for i in self.ingredients if i["name"] == name), None)

    def find_substitutions(self, ingredient, reason=None):
        result = []
        for sub in self.substitutions:
            if sub["ingredient"] in ingredient or ingredient in sub["ingredient"]:
                if reason is None:
                    result.append(sub)
                elif reason and sub.get("condition", "").lower() == reason.lower():
                    result.append(sub)
                elif not reason and sub.get("condition") in ["всегда", "любая"]:
                    result.append(sub)
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  RecipeAdapter (без изменений в логике)
# ─────────────────────────────────────────────────────────────────────────────

class RecipeAdapter:
    def __init__(self):
        self.manager = RecipeManager()
        self.substitution_confidence: Dict[str, float] = {}

    def parse_user_products(self, text: str) -> List[dict]:
        products = []
        for item in text.split(','):
            item = item.strip()
            if not item:
                continue
            is_canned = any(w in item for w in [
                'консервированный', 'консервированная', 'консервированное',
                'баночный', 'баночная', 'банка', 'банок'
            ])
            match = re.search(
                r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*'
                r'(банка|банки|банок|б|шт|г|мл|ст\.л|ч\.л|кг|л)?',
                item
            )
            if match:
                name = self.normalize_ingredient_name(match.group(1).strip().lower())
                quantity = float(match.group(2).replace(',', '.'))
                unit = match.group(3) or 'шт'
                if is_canned and unit == 'шт':
                    unit = 'банка'
                if unit in ['банка', 'банки', 'банок', 'б']:
                    unit = 'банка'
                products.append({'name': name, 'quantity': quantity, 'unit': unit})
            else:
                name = self.normalize_ingredient_name(item.lower())
                unit = 'банка' if is_canned else 'шт'
                products.append({'name': name, 'quantity': None, 'unit': unit})
        return products

    def _check_substitution_confidence(self, substitution, ingredient, dish_context=None):
        confidence = 0.8
        if dish_context and "яйц" in ingredient.get('name', ''):
            egg_role = dish_context.get('egg_role', 'general')
            sub_alt = substitution.get('alternative', '')
            if egg_role == 'leavening' and 'льняная' in sub_alt:
                confidence += 0.12
            elif egg_role == 'garnish' and 'тофу' in sub_alt:
                confidence += 0.10
            elif egg_role == 'garnish' and 'банан' in sub_alt:
                confidence -= 0.20
        if substitution.get('note') and len(substitution['note']) > 20:
            confidence += 0.05
        if substitution.get('ratio') and substitution['ratio'] != 1.0:
            confidence += 0.03
        key = f"{ingredient.get('name', '')}->{substitution.get('alternative', '')}"
        self.substitution_confidence[key] = round(min(confidence, 1.0), 2)
        return self.substitution_confidence[key]

    def _apply_substitution(self, ingredients, original_ing, substitution, scale_factor):
        if original_ing.get('by_taste', False):
            scale_factor = 1.0
            quantity_value = 0
        else:
            quantity_value = original_ing.get('quantity', 0) or 0

        unit_mapping = {
            'молоко': 'мл', 'вода': 'мл', 'масло растительное': 'мл',
            'соевое молоко': 'мл', 'миндальное молоко': 'мл',
            'кокосовое молоко': 'мл', 'кефир': 'мл', 'сливки': 'мл',
            'кокосовые сливки': 'мл', 'растительное молоко': 'мл', 'аквафаба': 'мл',
            'мука': 'г', 'рисовая мука': 'г', 'миндальная мука': 'г',
            'кокосовая мука': 'г', 'нутовая мука': 'г', 'гречневая мука': 'г',
            'крахмал': 'г', 'крахмал + вода': 'г', 'сахар': 'г', 'соль': 'г',
            'стевия': 'г', 'эритрит': 'г', 'какао': 'г', 'агар-агар': 'г',
            'горох': 'г', 'фасоль': 'г', 'кукуруза': 'г', 'нут отварной': 'г',
            'чечевица': 'г', 'тофу': 'г', 'тофу (мягкий)': 'г', 'тофу (плотный)': 'г',
            'творог': 'г', 'сыр': 'г', 'сметана': 'г', 'йогурт': 'г',
            'рикотта': 'г', 'маскарпоне': 'г', 'цветная капуста': 'г',
            'брокколи': 'г', 'кабачок': 'г', 'грибы': 'г', 'авокадо': 'г',
            'банан (пюре)': 'г', 'мясо': 'г', 'курица': 'г', 'сейтан': 'г',
            'веганский сыр': 'г', 'веганский майонез': 'г',
            'запечённая курица или говядина': 'г', 'греческий йогурт + горчица': 'г',
            'сметана + горчица': 'г', 'томатная паста + вода + специи': 'г',
            'кокосовый амино соус': 'мл', 'тамари': 'мл',
            'сироп агавы': 'мл', 'кленовый сироп': 'мл',
            'яйца': 'шт', 'лимон': 'шт', 'банан': 'шт',
        }

        def _detect_unit(name):
            n = name.lower()
            if any(k in n for k in ['мука', 'крахмал', 'тофу', 'капуста', 'брокколи',
                                     'кабачок', 'грибы', 'мясо', 'курица', 'нут', 'фасоль',
                                     'горох', 'чечевица', 'авокадо', 'кукуруза', 'паста', 'горчица']):
                return 'г'
            if any(k in n for k in ['молоко', 'сливки', 'кефир', 'вода', 'масло', 'соус', 'аквафаба']):
                return 'мл'
            if any(k in n for k in ['яйц', 'лимон', 'банан']):
                return 'шт'
            return None

        alt_name = substitution.get('alternative', '')
        alt_lower = alt_name.lower()

        if 'льняная' in alt_lower:
            new_unit = 'ст.л'
        elif 'сода + уксус' in alt_lower or 'сода + лимон' in alt_lower:
            new_unit = 'ч.л'
        elif alt_name in unit_mapping:
            new_unit = unit_mapping[alt_name]
        else:
            detected = _detect_unit(alt_name)
            new_unit = detected if detected else ('г' if original_ing.get('unit') == 'банка' else original_ing.get('unit', 'шт'))

        ratio = substitution.get('ratio', 1.0)

        if original_ing.get('unit') == 'банка':
            original_quantity_grams = can_to_grams(original_ing.get('name', ''), quantity_value)
            new_quantity = original_quantity_grams * scale_factor * ratio
            new_unit = 'г'
        else:
            new_quantity = quantity_value * scale_factor * ratio

        ing_name = original_ing.get('name', '')
        if 'яйц' in ing_name and 'льняная' in alt_name:
            new_quantity = quantity_value * 4
            new_unit = 'ст.л'
        elif ing_name == 'разрыхлитель' and 'сода + уксус' in alt_name:
            new_quantity = quantity_value * 0.5
            new_unit = 'ч.л'
        elif 'масло сливочное' in ing_name and 'растительное масло' in alt_name:
            new_quantity = quantity_value * 0.8
            new_unit = 'мл'

        if original_ing.get('by_taste', False):
            substitute = {'name': alt_name, 'quantity': None, 'unit': '', 'is_substitute': True,
                          'original_name': ing_name, 'by_taste': True}
        else:
            substitute = {'name': alt_name, 'quantity': round(new_quantity, 1), 'unit': new_unit,
                          'is_substitute': True, 'original_name': ing_name}

        for i, ing in enumerate(ingredients):
            if ing.get('name') == ing_name:
                ingredients[i] = substitute
                break

    def _calculate_servings(self, ingredients, manual_servings=None):
        if manual_servings and manual_servings > 0:
            return manual_servings
        total_weight = 0
        liquid_volume = 0
        for ing in ingredients:
            if ing.get('by_taste') or ing.get('quantity') is None:
                continue
            qty = ing['quantity']
            unit = ing.get('unit', '')
            if unit == 'банка':
                total_weight += can_to_grams(ing.get('name', ''), qty)
            elif unit == 'г':
                total_weight += qty
            elif unit == 'кг':
                total_weight += qty * 1000
            elif unit == 'мл':
                liquid_volume += qty
            elif unit == 'л':
                liquid_volume += qty * 1000
        if liquid_volume > total_weight * 0.5:
            servings = int((total_weight + liquid_volume) / 300)
        elif total_weight > 1000:
            servings = int(total_weight / 250)
        else:
            servings = int(total_weight / 150)
        return max(1, servings)

    def normalize_ingredient_name(self, name: str) -> str:
        name_lower = name.lower().strip()
        synonyms = {
            "горошек": "горох",
            "консервированный горох": "горох",
            "консервированный горошек": "горох", "баночный горох": "горох",
            "горох консервированный": "горох", "горошек консервированный": "горох",
            "горох в банке": "горох", "горошек в банке": "горох",
            "консервированная фасоль": "фасоль", "баночная фасоль": "фасоль",
            "фасоль в банке": "фасоль", "фасоль консервированная": "фасоль",
            "консервированный нут": "нут", "нут консервированный": "нут",
            "консервированная кукуруза": "кукуруза", "кукуруза в банке": "кукуруза",
            "сладкая кукуруза": "кукуруза", "кукуруза консервированная": "кукуруза",
            "коровье молоко": "молоко", "домашнее молоко": "молоко",
            "сливочное маслице": "масло сливочное",
            "куриное филе": "курица", "куриная грудка": "курица",
            "филе куриное": "курица", "грудка куриная": "курица",
            "свинина": "мясо", "говядина": "мясо",
            "картошка": "картофель", "картофелька": "картофель",
            "сладкий перец": "перец сладкий", "болгарский перец": "перец болгарский ",
            "острый перец": "перец острый",
            "репчатый лук": "лук репчатый",
            "зеленый лук": "лук зеленый",

        }
        if name_lower in synonyms:
            return synonyms[name_lower]
        for key, value in synonyms.items():
            if key in name_lower:
                return value
        return name_lower

    def _expand_allergies(self, allergies: list) -> list:
        ALLERGEN_GROUPS = {
            'молоко': ['молоко', 'лактоза'], 'молочка': ['молоко', 'лактоза'],
            'молочные': ['молоко', 'лактоза'], 'молочные продукты': ['молоко', 'лактоза'],
            'лактоза': ['лактоза', 'молоко'], 'казеин': ['молоко', 'лактоза'],
            'яйца': ['яйца'], 'яйцо': ['яйца'], 'белок яйца': ['яйца'], 'желток': ['яйца'],
            'глютен': ['глютен', 'пшеница'], 'пшеница': ['глютен', 'пшеница'],
            'злаки': ['глютен', 'пшеница', 'овёс'], 'рожь': ['глютен'], 'ячмень': ['глютен'],
            'овёс': ['глютен', 'овёс'],
            'орехи': ['орехи', 'миндаль', 'фундук', 'грецкие орехи', 'кешью'],
            'древесные орехи': ['орехи', 'миндаль', 'фундук', 'грецкие орехи', 'кешью'],
            'миндаль': ['орехи', 'миндаль'], 'фундук': ['орехи', 'фундук'],
            'грецкие орехи': ['орехи', 'грецкие орехи'], 'кешью': ['орехи', 'кешью'],
            'арахис': ['арахис'], 'соя': ['соя'], 'соевые': ['соя'], 'соевый': ['соя'],
            'рыба': ['рыба'], 'тунец': ['рыба'], 'лосось': ['рыба'],
            'ракообразные': ['ракообразные', 'морепродукты'],
            'морепродукты': ['ракообразные', 'моллюски', 'морепродукты'],
            'кунжут': ['кунжут'], 'горчица': ['горчица'], 'сельдерей': ['сельдерей'],
            'сульфиты': ['диоксид серы', 'сульфиты'],
        }
        expanded = []
        for a in allergies:
            a_l = a.lower().strip()
            if a_l in ALLERGEN_GROUPS:
                expanded.extend(ALLERGEN_GROUPS[a_l])
            else:
                expanded.append(a_l)
        return list(set(expanded))

    def adapt_recipe(self, recipe: dict, user_products_text: str,
                     allergies=None, diet=None) -> dict:
        has_user_products = bool(user_products_text and user_products_text.strip())
        if has_user_products:
            user_products = self.parse_user_products(user_products_text)
            user_dict = {p['name']: p for p in user_products}
        else:
            user_dict = {}

        recipe_ingredients = recipe['ingredients'].copy()
        processed_allergies = self._expand_allergies(allergies or [])
        dish_context = DishContextClassifier.classify(recipe.get('name', ''), recipe.get('category', ''))

        scale_factor = 1.0
        if has_user_products:
            min_scale = 1.0
            for ing in recipe_ingredients:
                if ing.get('by_taste') or ing.get('quantity') is None:
                    continue
                if ing['name'] in user_dict:
                    uq = user_dict[ing['name']]['quantity']
                    if uq is not None and uq > 0 and uq < ing['quantity']:
                        min_scale = min(min_scale, uq / ing['quantity'])
            scale_factor = min_scale
            max_scale = scale_factor
            for ing in recipe_ingredients:
                if ing.get('by_taste') or ing.get('quantity') is None:
                    continue
                if ing['name'] in user_dict:
                    uq = user_dict[ing['name']]['quantity']
                    if uq is not None and uq > 0 and uq > ing['quantity'] * scale_factor:
                        max_scale = max(max_scale, uq / ing['quantity'])
            scale_factor = max_scale

        scaled_ingredients = []
        missing, short, available, explicitly_missing, excess_info = [], [], [], [], []

        for ing in recipe_ingredients:
            if ing.get('by_taste', False):
                scaled_ingredients.append({**ing, 'quantity': None, 'unit': '', 'by_taste': True})
                continue
            if ing.get('quantity') is None:
                scaled_ingredients.append(ing)
                continue
            new_quantity = ing['quantity'] * scale_factor
            if ing['name'] in user_dict:
                uq = user_dict[ing['name']]['quantity']
                if uq is None:
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1)})
                elif uq == 0:
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1), 'missing': True})
                    explicitly_missing.append(ing)
                    missing.append(ing)
                elif uq >= new_quantity:
                    if uq > new_quantity * 1.05:
                        excess_info.append({'name': ing['name'], 'recipe_needs': round(new_quantity, 1),
                                            'user_has': uq, 'excess': round(uq - new_quantity, 1), 'unit': ing['unit']})
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1)})
                    available.append(ing)
                else:
                    scaled_ingredients.append({**ing, 'quantity': uq, 'limited': True,
                                               'original_quantity': round(new_quantity, 1)})
                    short.append({**ing, 'user_quantity': uq, 'shortage': ing['quantity'] - uq})
            else:
                if has_user_products:
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1), 'missing': True})
                    missing.append(ing)
                else:
                    scaled_ingredients.append({**ing, 'quantity': round(ing['quantity'], 1)})
                    available.append(ing)

        diet_issues = []
        if diet and diet != "Нет":
            for ing in recipe_ingredients:
                compatible, _, _ = diet_analyzer.check_compatibility(ing, diet, dish_context=dish_context)
                if not compatible and not any(d['name'] == ing['name'] for d in diet_issues):
                    diet_issues.append({**ing, 'diet': diet})

        problem_allergies = []
        if processed_allergies:
            for ing in recipe_ingredients:
                ing_info = self.manager.get_ingredient_info(ing['name'])
                if ing_info and ing_info.get('allergens'):
                    for allergen in processed_allergies:
                        if allergen.lower() in [a.lower() for a in ing_info['allergens']]:
                            if not any(pa['name'] == ing['name'] for pa in problem_allergies):
                                problem_allergies.append({**ing, 'allergen': allergen, 'info': ing_info})

        issues_to_resolve = {}
        for ing in diet_issues:
            issues_to_resolve.setdefault(ing['name'], {'ingredient': ing, 'reasons': []})
            issues_to_resolve[ing['name']]['reasons'].append(f"diet_{diet}")
        for ing in problem_allergies:
            issues_to_resolve.setdefault(ing['name'], {'ingredient': ing, 'reasons': []})
            issues_to_resolve[ing['name']]['reasons'].append(f"allergy_{ing['allergen']}")
        for ing in explicitly_missing:
            issues_to_resolve.setdefault(ing['name'], {'ingredient': ing, 'reasons': []})
            issues_to_resolve[ing['name']]['reasons'].append('explicitly_missing')

        substitutions_made = []
        alternatives_for_display = []

        for key, issue_data in issues_to_resolve.items():
            ing = issue_data['ingredient']
            reasons = issue_data['reasons']
            search_reason = None
            if any('allergy_' in r for r in reasons):
                search_reason = next((r.replace('allergy_', '') for r in reasons if r.startswith('allergy_')), None)
            elif any('diet_' in r for r in reasons):
                search_reason = diet

            context_alts = diet_analyzer.find_alternatives(ing['name'], search_reason, dish_context=dish_context)
            db_subs = self.manager.find_substitutions(ing['name'], search_reason)
            ingredient_alternatives = []
            best_sub = None
            best_confidence = 0.0

            for alt in context_alts:
                fake_sub = {'ingredient': ing['name'], 'alternative': alt['name'],
                            'ratio': alt.get('ratio', 1.0), 'note': alt.get('description', ''),
                            'condition': search_reason or 'всегда'}
                conf = self._check_substitution_confidence(fake_sub, ing, dish_context)
                ingredient_alternatives.append({'name': alt['name'], 'ratio': alt.get('ratio', 1.0),
                                                'note': alt.get('description', ''), 'confidence': conf,
                                                'condition': search_reason or 'всегда'})
                if conf > best_confidence:
                    best_confidence = conf
                    best_sub = fake_sub

            for sub in db_subs:
                conf = self._check_substitution_confidence(sub, ing, dish_context)
                alt_name = sub['alternative']
                if not any(a['name'] == alt_name for a in ingredient_alternatives):
                    ingredient_alternatives.append({'name': alt_name, 'ratio': sub.get('ratio', 1.0),
                                                    'note': sub.get('note', ''), 'confidence': conf,
                                                    'condition': sub.get('condition', 'всегда')})
                    if conf > best_confidence:
                        best_confidence = conf
                        best_sub = sub

            if ingredient_alternatives:
                alternatives_for_display.append({'original': ing['name'],
                                                  'alternatives': sorted(ingredient_alternatives, key=lambda x: x['confidence'], reverse=True)})

            if best_sub and best_confidence > 0.5:
                reason_text = []
                for r in reasons:
                    if r.startswith('allergy_'):
                        reason_text.append(f"аллергия на {r.replace('allergy_', '')}")
                    elif r.startswith('diet_'):
                        reason_text.append(f"диета {diet}")
                    elif r == 'explicitly_missing':
                        reason_text.append("указано с 0")
                substitutions_made.append({'original': ing['name'],
                                           'alternative': best_sub.get('alternative', best_sub.get('name', '')),
                                           'reason': ", ".join(reason_text), 'note': best_sub.get('note', best_sub.get('description', '')),
                                           'confidence': best_confidence, 'ratio': best_sub.get('ratio', 1.0)})
                self._apply_substitution(scaled_ingredients, ing, best_sub, scale_factor)

        manual_servings = recipe.get('servings')
        servings = self._calculate_servings(scaled_ingredients, manual_servings)
        issues_for_check = []
        for ing in diet_issues + problem_allergies:
            best = next((s for s in substitutions_made if s['original'] == ing['name']), None)
            issues_for_check.append({'name': ing['name'], 'best_sub_name': best['alternative'] if best else ''})
        feasibility = AdaptationFeasibilityChecker.check(recipe, issues_for_check, dish_context)

        return {
            'recipe_name': recipe['name'], 'ingredients': scaled_ingredients,
            'missing': missing, 'explicitly_missing': explicitly_missing,
            'short': short, 'available': available, 'excess': excess_info,
            'diet_issues': diet_issues, 'allergy_issues': problem_allergies,
            'substitutions': substitutions_made, 'alternatives': alternatives_for_display,
            'scale_factor': scale_factor, 'steps': recipe.get('steps', []),
            'servings': servings, 'dish_context': dish_context, 'feasibility': feasibility,
        }

    def _parse_recipe_text(self, text: str) -> list:
        ingredients = []
        taste_phrases = ['по вкусу', 'по желанию', 'опционально', 'по необходимости']
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            is_by_taste = any(p in line.lower() for p in taste_phrases)
            match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?', line)
            if match:
                name = self.normalize_ingredient_name(match.group(1).strip().lower())
                qty = float(match.group(2).replace(',', '.'))
                unit = match.group(3) or 'шт'
                if unit in ['банка', 'банки', 'банок', 'б']:
                    unit = 'банка'
                ingredients.append({'name': name, 'quantity': qty, 'unit': unit, 'by_taste': False})
            else:
                clean = line.lower()
                for p in taste_phrases:
                    clean = clean.replace(p, '').strip()
                name = self.normalize_ingredient_name(clean or line.lower())
                ingredients.append({'name': name, 'quantity': None, 'unit': '', 'by_taste': True})
        return ingredients


# ─────────────────────────────────────────────────────────────────────────────
#  Вспомогательные UI-функции
# ─────────────────────────────────────────────────────────────────────────────

def parse_ingredients_text(text: str, adapter: RecipeAdapter) -> tuple:
    """Парсит текст ингредиентов, возвращает (список, ошибки)."""
    ingredients = []
    invalid_lines = []
    taste_phrases = ['по вкусу', 'по желанию', 'опционально', 'по необходимости']
    for line in text.strip().split('\n'):
        line = line.strip().replace(',', '')
        if not line:
            continue
        is_by_taste = any(p in line.lower() for p in taste_phrases)
        match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?', line)
        if match:
            name = adapter.normalize_ingredient_name(match.group(1).strip().lower())
            qty = float(match.group(2).replace(',', '.'))
            unit = match.group(3) or 'шт'
            if unit in ['банка', 'банки', 'банок', 'б']:
                unit = 'банка'
            ingredients.append({'name': name, 'quantity': qty, 'unit': unit, 'by_taste': False})
        elif is_by_taste:
            clean = line.lower()
            for p in taste_phrases:
                clean = clean.replace(p, '').strip()
            name = adapter.normalize_ingredient_name(clean or line.lower())
            ingredients.append({'name': name, 'quantity': None, 'unit': '', 'by_taste': True})
        else:
            invalid_lines.append(line)
    return ingredients, invalid_lines


def show_result(result: dict):
    """Отображает результат адаптации."""
    st.markdown(f"## {result['recipe_name']}")

    dctx = result.get('dish_context', {})
    if dctx.get('egg_role') and dctx['egg_role'] != 'general':
        label = DishContextClassifier.egg_role_label(dctx['egg_role'])
        if label:
            st.info(label)

    feas = result.get('feasibility', {})
    if feas.get('impossible_reasons'):
        st.error("**Адаптация частично невозможна:**")
        for reason in feas['impossible_reasons']:
            st.error(reason)
        if feas.get('alternative_dishes'):
            st.markdown("### 🍽️ Рекомендуемые альтернативные блюда:")
            for alt in feas['alternative_dishes']:
                st.success(f"**{alt['name']}** — {alt['note']}")
    elif feas.get('warnings'):
        for w in feas['warnings']:
            st.warning(w)
        if feas.get('alternative_dishes'):
            with st.expander("🍽️ Альтернативные блюда без проблемных ингредиентов"):
                for alt in feas['alternative_dishes']:
                    st.write(f"• **{alt['name']}** — {alt['note']}")

    st.markdown(f"### Примерно на **{result['servings']}** персон")

    if result['scale_factor'] != 1.0:
        if result['scale_factor'] < 1.0:
            st.info(f"**Рецепт уменьшен на {int((1 - result['scale_factor']) * 100)}%**")
        else:
            st.info(f"**Рецепт увеличен в {result['scale_factor']:.1f} раз**")

    col_a, col_b = st.columns(2)
    with col_a:
        if result['excess']:
            with st.expander("📦 Избыток продуктов"):
                for e in result['excess']:
                    st.write(f"• {e['name']}: нужно {e['recipe_needs']}{e['unit']}, у вас {e['user_has']}{e['unit']} (останется {e['excess']}{e['unit']})")
        if result['short']:
            with st.expander("⚠️ Продуктов меньше нормы"):
                for s in result['short']:
                    st.write(f"• {s['name']}: нужно {s['quantity']}{s['unit']}, есть {s['user_quantity']}{s['unit']}")
                st.info("💡 Если продукта нет совсем — укажи его с 0")
    with col_b:
        if result['allergy_issues']:
            with st.expander("🚫 Аллергены"):
                for a in result['allergy_issues']:
                    st.write(f"• {a['name']} содержит аллерген: {a['allergen']}")
        if result['diet_issues']:
            with st.expander("🥗 Проблемы с диетой"):
                for d in result['diet_issues']:
                    st.write(f"• {d['name']} не соответствует диете {d['diet']}")

    if result['substitutions']:
        with st.expander("🔄 Произведённые замены"):
            for sub in result['substitutions']:
                st.write(f"• **{sub['original']}** → **{sub['alternative']}**")
                st.caption(f"  Причина: {sub['reason']}")
                if sub['note']:
                    st.caption(f"  ⓘ {sub['note']}")

    if result.get('alternatives'):
        with st.expander("💡 Другие доступные альтернативы"):
            for alt_group in result['alternatives']:
                if len(alt_group['alternatives']) > 1:
                    st.markdown(f"**{alt_group['original']}** → можно заменить на:")
                    for alt in alt_group['alternatives']:
                        is_selected = any(s['original'] == alt_group['original'] and s['alternative'] == alt['name']
                                          for s in result['substitutions'])
                        if not is_selected:
                            pct = int(alt['confidence'] * 100)
                            st.markdown(f"  • **{alt['name']}** (уверенность ИИ: {pct}%)")
                            if alt['note']:
                                st.caption(f"    ⓘ {alt['note']}")
                    st.markdown("---")

    st.markdown("### Ингредиенты после адаптации:")
    for ing in result['ingredients']:
        c1, c2, c3 = st.columns([3, 1, 2])
        with c1:
            if ing.get('is_substitute'):
                st.markdown(f"**{ing['name']}** 🔄")
            elif ing.get('limited'):
                st.markdown(f"**{ing['name']}** ⚠️")
            elif ing.get('missing'):
                st.markdown(f"~~{ing['name']}~~ ❌")
            else:
                st.markdown(f"**{ing['name']}**")
        with c2:
            if ing.get('by_taste'):
                st.markdown("по вкусу")
            elif ing.get('unit') == 'банка':
                grams = can_to_grams(ing.get('name', ''), ing['quantity'])
                st.markdown(f"{ing['quantity']} банка (≈{int(grams)}г)")
            else:
                st.markdown(f"{ing.get('quantity', '?')}{ing.get('unit', '')}")
        with c3:
            if ing.get('original_name'):
                st.caption(f"замена {ing['original_name']}")
            elif ing.get('limited'):
                st.caption(f"нужно {ing['original_quantity']}{ing.get('unit', '')}")

    # КБЖУ
    nutrition = calculate_nutrition(result['ingredients'])
    if nutrition['ккал'] > 0:
        st.markdown("### 📊 Примерная пищевая ценность (на всё блюдо):")
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Калории", f"{int(nutrition['ккал'])} ккал")
        n2.metric("Белки", f"{nutrition['белки']} г")
        n3.metric("Жиры", f"{nutrition['жиры']} г")
        n4.metric("Углеводы", f"{nutrition['углеводы']} г")
        if result['servings'] > 1:
            st.caption(f"На 1 порцию: {int(nutrition['ккал'] / result['servings'])} ккал / "
                       f"Б: {round(nutrition['белки'] / result['servings'], 1)}г / "
                       f"Ж: {round(nutrition['жиры'] / result['servings'], 1)}г / "
                       f"У: {round(nutrition['углеводы'] / result['servings'], 1)}г")

    if result['steps']:
        with st.expander("📋 Шаги приготовления"):
            for i, step in enumerate(result['steps'], 1):
                st.write(f"{i}. {step}")

    # Экспорт рецепта
    with st.expander("📤 Экспорт рецепта"):
        lines = [f"# {result['recipe_name']}", f"Порций: ~{result['servings']}", "", "## Ингредиенты:"]
        for ing in result['ingredients']:
            if ing.get('by_taste'):
                lines.append(f"- {ing['name']} — по вкусу")
            elif ing.get('unit') == 'банка':
                lines.append(f"- {ing['name']} — {ing['quantity']} банка")
            else:
                lines.append(f"- {ing['name']} — {ing.get('quantity', '?')} {ing.get('unit', '')}")
        if result['steps']:
            lines.append("\n## Приготовление:")
            for i, step in enumerate(result['steps'], 1):
                lines.append(f"{i}. {step}")
        if result['substitutions']:
            lines.append("\n## Замены:")
            for sub in result['substitutions']:
                lines.append(f"- {sub['original']} → {sub['alternative']}")
        export_text = "\n".join(lines)
        st.text_area("Скопируй текст рецепта:", export_text, height=200)


# ─────────────────────────────────────────────────────────────────────────────
#  Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

adapter = RecipeAdapter()

st.set_page_config(page_title="Умный адаптер рецептов", page_icon="🍳", layout="wide")
load_css()

st.markdown('<h1 class="main-header">🍳 Умный адаптер рецептов</h1>', unsafe_allow_html=True)

# ── Инициализация session state ───────────────────────────────────────────
if 'adaptation_history' not in st.session_state:
    st.session_state.adaptation_history = []
if 'edit_recipe_id' not in st.session_state:
    st.session_state.edit_recipe_id = None
if 'delete_confirm_id' not in st.session_state:
    st.session_state.delete_confirm_id = None

# ── Сайдбар ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ℹ️ Навигация")
    with st.expander("Как это работает", expanded=False):
        st.markdown("""
        1. **Выбери рецепт** из базы
        2. **Укажи продукты**, которые есть
        3. **Добавь аллергии** и диету
        4. **Получи адаптированный рецепт** с заменами и КБЖУ!

        **Совет:** Если оставить поле продуктов пустым — считается, что всё есть.
        Если продукта нет совсем — укажи `0` (например: `яйца 0 шт`).
        """)

    with st.expander("Где используется ИИ", expanded=False):
        st.write("• Контекстный анализ типа блюда")
        st.write("• Умные замены с учётом роли ингредиента")
        st.write("• Оценка уверенности в замене")
        st.write("• Расчёт оптимальных пропорций")
        st.write("• Конвертация банок в граммы")
        st.write("• Расчёт КБЖУ")
        st.write("• Поиск рецептов по продуктам")

    with st.expander("Управление базой данных", expanded=False):
        if st.button("🔄 Восстановить базовые рецепты"):
            default_recipes = {
                "recipes": [
                    {"id": 1, "name": "Шоколадный торт", "category": "десерты",
                     "ingredients": [{"name": "мука", "quantity": 300, "unit": "г"}, {"name": "яйца", "quantity": 3, "unit": "шт"},
                                     {"name": "молоко", "quantity": 200, "unit": "мл"}, {"name": "сахар", "quantity": 150, "unit": "г"},
                                     {"name": "масло сливочное", "quantity": 100, "unit": "г"}, {"name": "разрыхлитель", "quantity": 10, "unit": "г"},
                                     {"name": "какао", "quantity": 50, "unit": "г"}],
                     "steps": ["Смешать сухие ингредиенты", "Добавить яйца и молоко", "Выпекать 30 мин при 180°C"],
                     "time": 60, "difficulty": "средняя"},
                    {"id": 2, "name": "Блины", "category": "завтраки",
                     "ingredients": [{"name": "мука", "quantity": 200, "unit": "г"}, {"name": "молоко", "quantity": 500, "unit": "мл"},
                                     {"name": "яйца", "quantity": 2, "unit": "шт"}, {"name": "сахар", "quantity": 20, "unit": "г"},
                                     {"name": "масло растительное", "quantity": 30, "unit": "мл"}, {"name": "соль", "quantity": 2, "unit": "г"}],
                     "steps": ["Смешать все ингредиенты", "Жарить на сковороде"],
                     "time": 30, "difficulty": "легкая"},
                    {"id": 3, "name": "Сырники", "category": "завтраки",
                     "ingredients": [{"name": "творог", "quantity": 500, "unit": "г"}, {"name": "яйца", "quantity": 1, "unit": "шт"},
                                     {"name": "мука", "quantity": 100, "unit": "г"}, {"name": "сахар", "quantity": 50, "unit": "г"},
                                     {"name": "соль", "quantity": 1, "unit": "г"}],
                     "steps": ["Смешать творог с яйцом", "Добавить муку и сахар", "Обжарить на сковороде"],
                     "time": 40, "difficulty": "легкая"},
                    {"id": 4, "name": "Салат \"Оливье\"", "category": "салаты",
                     "ingredients": [{"name": "картофель", "quantity": 400.0, "unit": "г"}, {"name": "яйца", "quantity": 6.0, "unit": "шт"},
                                     {"name": "огурцы соленые", "quantity": 300.0, "unit": "г"}, {"name": "колбаса", "quantity": 300.0, "unit": "г"},
                                     {"name": "майонез", "quantity": 300.0, "unit": "мл"}, {"name": "горох", "quantity": 1.0, "unit": "банка"}],
                     "steps": ["Отварить яйца и картофель", "Нарезать кубиком картофель, яйца, огурцы и колбасу",
                                "Смешать все ингредиенты в миске, заправить майонезом"],
                     "time": 30, "difficulty": "легкая"},
                    {"id": 5, "name": "Омлет с помидором", "category": "завтраки",
                     "ingredients": [{"name": "яйца", "quantity": 2.0, "unit": "шт", "by_taste": False},
                                     {"name": "помидор", "quantity": 1.0, "unit": "шт", "by_taste": False},
                                     {"name": "соль", "quantity": None, "unit": "", "by_taste": True},
                                     {"name": "майонез", "quantity": None, "unit": "", "by_taste": True}],
                     "steps": ["Промыть и нарезать помидор", "Взбить яйца с солью", "Жарить яйца вместе с помидором до готовности"],
                     "time": 5, "difficulty": "легкая", "servings": 1}
                ]
            }
            with open("data/recipes.json", 'w', encoding='utf-8') as f:
                json.dump(default_recipes, f, ensure_ascii=False, indent=2)
            st.success("Базовые рецепты восстановлены!")
            st.rerun()

    # История адаптаций
    if st.session_state.adaptation_history:
        with st.expander(f"🕒 История адаптаций ({len(st.session_state.adaptation_history)})", expanded=False):
            for i, h in enumerate(reversed(st.session_state.adaptation_history[-10:])):
                st.caption(f"**{h['recipe']}** — {h['time']}")
                if h.get('diet') and h['diet'] != 'Нет':
                    st.caption(f"Диета: {h['diet']}")
            if st.button("Очистить историю"):
                st.session_state.adaptation_history = []
                st.rerun()


# ── Вкладки ───────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Выбрать из базы",
    "🧲 Поиск по продуктам",
    "✏️ Управление рецептами",
    "➕ Добавить рецепт",
])


# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 1: Выбор рецепта
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.header("Выбери рецепт из базы")
    col1, col2 = st.columns([1, 1])

    with col1:
        search_query = st.text_input("🔎 Поиск по названию", key="search_tab1")
        all_recipes = adapter.manager.get_all_recipes()

        if search_query:
            filtered_recipes = [r for r in all_recipes if search_query.lower() in r['name'].lower()]
        else:
            categories = sorted(set(r.get('category', 'другие') for r in all_recipes))
            selected_category = st.selectbox("Категория", ["Все"] + categories, key="cat_tab1")
            filtered_recipes = all_recipes if selected_category == "Все" else [r for r in all_recipes if r.get('category') == selected_category]

    with col2:
        if filtered_recipes:
            recipe_names = [r['name'] for r in filtered_recipes]
            selected_name = st.selectbox("Выбери рецепт", recipe_names, key="recipe_tab1")
            selected_recipe = next(r for r in filtered_recipes if r['name'] == selected_name)

            ctx = DishContextClassifier.classify(selected_recipe.get('name', ''), selected_recipe.get('category', ''))
            dish_type_label = []
            if ctx['is_sweet']:
                dish_type_label.append("🍰 Выпечка/Десерт")
            if ctx['is_savory']:
                dish_type_label.append("🥗 Несладкое блюдо")
            if dish_type_label:
                st.caption("Тип блюда: " + " | ".join(dish_type_label))

            time_val = selected_recipe.get('time')
            diff_val = selected_recipe.get('difficulty', '')
            if time_val or diff_val:
                st.caption(f"⏱ {time_val} мин  •  Сложность: {diff_val}")

            st.markdown("**Ингредиенты:**")
            for ing in selected_recipe['ingredients']:
                if ing.get('by_taste', False):
                    st.markdown(f"• {ing['name']} (по вкусу)")
                elif ing.get('unit') == 'банка':
                    grams = can_to_grams(ing['name'], ing['quantity'])
                    st.markdown(f"• {ing['name']}: {ing['quantity']} банка (≈{int(grams)} г)")
                else:
                    st.markdown(f"• {ing['name']}: {ing['quantity']} {ing['unit']}")
        else:
            st.warning("Рецепты не найдены")

    if filtered_recipes and 'selected_recipe' in locals():
        st.markdown("---")
        st.subheader("Какие продукты у тебя есть?")
        user_products = st.text_area(
            "Введи продукты через запятую",
            placeholder="мука 500г, яйца 3 шт, молоко 200мл, горох 1 банка, разрыхлитель 0г",
            key="products_tab1", height=80,
            help="Формат: продукт количество единица\nОставь пустым — считается, что всё есть\nЕсли продукта нет — укажи 0"
        )
        col1, col2 = st.columns(2)
        with col1:
            allergies_input = st.text_input("🚫 Аллергии (через запятую)", placeholder="лактоза, глютен, яйца", key="allergy_tab1")
        with col2:
            diet = st.selectbox("🥗 Диета", ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"], key="diet_tab1")

        if st.button("🚀 Адаптировать", type="primary", use_container_width=True, key="adapt_tab1"):
            allergies = [a.strip().lower() for a in allergies_input.split(',') if a.strip()] if allergies_input else []
            with st.spinner("ИИ анализирует рецепт..."):
                result = adapter.adapt_recipe(selected_recipe, user_products or "", allergies, diet)
            # Сохраняем в историю
            st.session_state.adaptation_history.append({
                'recipe': result['recipe_name'],
                'diet': diet,
                'time': datetime.now().strftime('%H:%M'),
            })
            st.markdown("---")
            show_result(result)


# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 2: Поиск по продуктам
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("🧲 Что приготовить из того, что есть?")
    st.write("Введи продукты — система найдёт подходящие рецепты и покажет, чего не хватает.")

    products_input = st.text_area(
        "Твои продукты",
        placeholder="мука, яйца, молоко, картофель, лук, масло растительное",
        height=80, key="products_tab2"
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        min_match_pct = st.slider("Минимальный % совпадения ингредиентов", 0, 100, 30, 10)
    with col2:
        show_top = st.selectbox("Показать топ", [5, 10, 15, 20], index=0)

    if st.button("🔍 Найти рецепты", type="primary", key="search_products"):
        if products_input.strip():
            user_products_list = adapter.parse_user_products(products_input)
            results = adapter.manager.search_by_available_ingredients(user_products_list)
            filtered = [r for r in results if r['pct'] >= min_match_pct][:show_top]

            if filtered:
                st.success(f"Найдено {len(filtered)} рецептов (из {len(results)} в базе)")
                for res in filtered:
                    recipe = res['recipe']
                    pct = res['pct']
                    color = "🟢" if pct >= 80 else "🟡" if pct >= 50 else "🔴"

                    with st.expander(f"{color} **{recipe['name']}** — {pct}% ингредиентов есть"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Есть", f"{res['matched']}/{res['total']}")
                        c2.metric("Не хватает", res['missing'])
                        c3.metric("Совпадение", f"{pct}%")

                        # Показываем что есть и чего нет
                        user_names = {p['name'].lower() for p in user_products_list}
                        have, need = [], []
                        for ing in recipe.get('ingredients', []):
                            if ing.get('by_taste') or ing.get('quantity') is None:
                                continue
                            name_lower = ing['name'].lower()
                            if any(u in name_lower or name_lower in u for u in user_names):
                                have.append(ing['name'])
                            else:
                                need.append(ing['name'])

                        col_h, col_n = st.columns(2)
                        with col_h:
                            if have:
                                st.markdown("**✅ Есть:**")
                                for h in have:
                                    st.markdown(f"• {h}")
                        with col_n:
                            if need:
                                st.markdown("**🛒 Докупить:**")
                                for n in need:
                                    st.markdown(f"• {n}")

                        if st.button(f"Адаптировать этот рецепт", key=f"adapt_search_{recipe.get('id', 0)}"):
                            with st.spinner("ИИ анализирует..."):
                                result = adapter.adapt_recipe(recipe, products_input, [], "Нет")
                            st.session_state.adaptation_history.append({
                                'recipe': result['recipe_name'], 'diet': 'Нет',
                                'time': datetime.now().strftime('%H:%M'),
                            })
                            show_result(result)
            else:
                st.warning(f"Нет рецептов с совпадением ≥ {min_match_pct}%. Попробуй снизить порог.")
        else:
            st.error("Введи хотя бы один продукт!")


# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 3: Управление рецептами (редактирование и удаление)
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("✏️ Управление рецептами")
    all_recipes_manage = adapter.manager.get_all_recipes()

    if not all_recipes_manage:
        st.info("База рецептов пуста.")
    else:
        # Выбор рецепта для управления
        recipe_options = {r['name']: r for r in all_recipes_manage}
        selected_manage_name = st.selectbox("Выбери рецепт", list(recipe_options.keys()), key="manage_select")
        managing_recipe = recipe_options[selected_manage_name]

        col_edit, col_del, col_dup = st.columns(3)
        with col_edit:
            if st.button("✏️ Редактировать", use_container_width=True):
                st.session_state.edit_recipe_id = managing_recipe.get('id')
                st.session_state.delete_confirm_id = None
        with col_del:
            if st.button("🗑️ Удалить", use_container_width=True, type="secondary"):
                st.session_state.delete_confirm_id = managing_recipe.get('id')
                st.session_state.edit_recipe_id = None
        with col_dup:
            if st.button("📋 Дублировать", use_container_width=True):
                new_recipe = managing_recipe.copy()
                new_recipe['name'] = managing_recipe['name'] + " (копия)"
                new_recipe.pop('id', None)
                nid = adapter.manager.add_recipe(new_recipe)
                if nid:
                    st.success(f"Рецепт скопирован с ID {nid}!")
                    st.rerun()
                else:
                    st.error("Такое имя уже существует!")

        st.markdown("---")

        # ── Подтверждение удаления ─────────────────────────────────────────
        if st.session_state.delete_confirm_id == managing_recipe.get('id'):
            st.error(f"⚠️ Удалить рецепт **\"{managing_recipe['name']}\"**? Это действие необратимо.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Да, удалить", type="primary", use_container_width=True):
                    success = adapter.manager.delete_recipe(managing_recipe['id'])
                    if success:
                        st.success("Рецепт удалён!")
                        st.session_state.delete_confirm_id = None
                        st.rerun()
                    else:
                        st.error("Ошибка при удалении")
            with c2:
                if st.button("❌ Отмена", use_container_width=True):
                    st.session_state.delete_confirm_id = None
                    st.rerun()

        # ── Форма редактирования ───────────────────────────────────────────
        elif st.session_state.edit_recipe_id == managing_recipe.get('id'):
            st.subheader(f"Редактирование: {managing_recipe['name']}")

            with st.form(f"edit_form_{managing_recipe['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Название", value=managing_recipe['name'])
                with col2:
                    new_servings = st.number_input("Порций", min_value=1,
                                                    value=managing_recipe.get('servings', 2))
                new_category = st.selectbox("Категория",
                    ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"],
                    index=["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"].index(
                        managing_recipe.get('category', 'другие'))
                    if managing_recipe.get('category') in ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"] else 0)

                # Предзаполнение ингредиентов
                existing_ing_lines = []
                for ing in managing_recipe.get('ingredients', []):
                    if ing.get('by_taste') or ing.get('quantity') is None:
                        existing_ing_lines.append(f"{ing['name']} по вкусу")
                    elif ing.get('unit') == 'банка':
                        existing_ing_lines.append(f"{ing['name']} {ing['quantity']} банка")
                    else:
                        existing_ing_lines.append(f"{ing['name']} {ing['quantity']}{ing.get('unit', 'г')}")
                existing_ing_text = "\n".join(existing_ing_lines)

                new_ingredients_text = st.text_area("Ингредиенты (каждый с новой строки)",
                                                      value=existing_ing_text, height=180)
                new_steps_text = st.text_area("Шаги приготовления (каждый с новой строки)",
                                               value="\n".join(managing_recipe.get('steps', [])), height=150)

                col_t, col_d = st.columns(2)
                with col_t:
                    new_time = st.number_input("Время (мин)", min_value=1, value=managing_recipe.get('time', 30))
                with col_d:
                    diff_opts = ["легкая", "средняя", "сложная"]
                    cur_diff = managing_recipe.get('difficulty', 'средняя')
                    new_difficulty = st.selectbox("Сложность", diff_opts,
                                                   index=diff_opts.index(cur_diff) if cur_diff in diff_opts else 1)

                save_col, cancel_col = st.columns(2)
                with save_col:
                    save_btn = st.form_submit_button("💾 Сохранить изменения", type="primary", use_container_width=True)
                with cancel_col:
                    cancel_btn = st.form_submit_button("❌ Отмена", use_container_width=True)

                if save_btn:
                    new_ingredients, invalid = parse_ingredients_text(new_ingredients_text, adapter)
                    if invalid:
                        st.warning(f"Не удалось распознать строки: {', '.join(invalid)}")
                    if new_name and new_ingredients:
                        new_steps = [s.strip() for s in new_steps_text.strip().split('\n') if s.strip()]
                        updated = {
                            'name': new_name, 'category': new_category,
                            'ingredients': new_ingredients, 'steps': new_steps,
                            'time': new_time, 'difficulty': new_difficulty,
                            'servings': new_servings,
                        }
                        if adapter.manager.update_recipe(managing_recipe['id'], updated):
                            st.success(f"Рецепт \"{new_name}\" успешно обновлён!")
                            st.session_state.edit_recipe_id = None
                            st.rerun()
                        else:
                            st.error("Ошибка при сохранении")
                    else:
                        st.error("Заполните название и ингредиенты!")

                if cancel_btn:
                    st.session_state.edit_recipe_id = None
                    st.rerun()

        else:
            # Превью рецепта
            st.markdown(f"**Категория:** {managing_recipe.get('category', '—')} "
                        f"• **Время:** {managing_recipe.get('time', '?')} мин "
                        f"• **Сложность:** {managing_recipe.get('difficulty', '?')}")
            st.markdown("**Ингредиенты:**")
            for ing in managing_recipe.get('ingredients', []):
                if ing.get('by_taste'):
                    st.markdown(f"• {ing['name']} — по вкусу")
                elif ing.get('unit') == 'банка':
                    st.markdown(f"• {ing['name']} — {ing['quantity']} банка")
                else:
                    st.markdown(f"• {ing['name']} — {ing.get('quantity', '?')} {ing.get('unit', '')}")
            if managing_recipe.get('steps'):
                with st.expander("Шаги приготовления"):
                    for i, step in enumerate(managing_recipe['steps'], 1):
                        st.write(f"{i}. {step}")


# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 4: Добавить рецепт
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.header("➕ Добавить новый рецепт")

    with st.form("add_recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("Название рецепта")
        with col2:
            servings_manual = st.number_input("Количество порций", min_value=1, value=2)

        category = st.selectbox("Категория",
            ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"])

        if recipe_name:
            ctx_preview = DishContextClassifier.classify(recipe_name, category)
            if ctx_preview['is_sweet']:
                st.caption("🍰 Определён как выпечка/десерт — замены яиц будут для выпечки")
            elif ctx_preview['is_savory']:
                st.caption("🥗 Определён как несладкое блюдо — замены яиц будут для горячего/салатов")

        st.subheader("Ингредиенты")
        ingredients_text = st.text_area(
            "Ингредиенты (каждый с новой строки)",
            placeholder="мука 200г\nяйца 2 шт\nмолоко 100мл\nсоль по вкусу\nгорох 1 банка",
            height=150,
            help="Формат: название количество единица. Банки: 'горох 1 банка'"
        )

        st.subheader("Шаги приготовления")
        steps_text = st.text_area("Каждый шаг с новой строки",
            placeholder="Смешать сухие ингредиенты\nДобавить яйца и молоко\nВыпекать 30 мин", height=150)

        col1, col2 = st.columns(2)
        with col1:
            time_val = st.number_input("Время приготовления (мин)", min_value=5, value=30)
        with col2:
            difficulty = st.selectbox("Сложность", ["легкая", "средняя", "сложная"])

        submitted = st.form_submit_button("💾 Сохранить рецепт", type="primary", use_container_width=True)

        if submitted:
            if recipe_name and ingredients_text:
                existing_names = [r['name'].lower() for r in adapter.manager.get_all_recipes()]
                if recipe_name.lower() in existing_names:
                    st.error(f"Рецепт '{recipe_name}' уже существует!")
                else:
                    ingredients, invalid_lines = parse_ingredients_text(ingredients_text, adapter)
                    if invalid_lines:
                        st.warning(f"Не удалось распознать: {', '.join(invalid_lines)}")
                    steps = [s.strip() for s in steps_text.strip().split('\n') if s.strip()]
                    if ingredients:
                        new_recipe = {'name': recipe_name, 'category': category,
                                      'ingredients': ingredients, 'steps': steps,
                                      'time': time_val, 'difficulty': difficulty,
                                      'servings': servings_manual}
                        recipe_id = adapter.manager.add_recipe(new_recipe)
                        if recipe_id:
                            st.success(f"Рецепт '{recipe_name}' успешно добавлен (ID: {recipe_id})!")
                            st.rerun()
                        else:
                            st.error("Ошибка при добавлении рецепта!")
                    else:
                        st.error("Не удалось распознать ингредиенты! Проверьте формат.")
            else:
                st.error("Заполните название и ингредиенты!")

st.markdown("---")
st.markdown("<center>🍳 Умный адаптер рецептов — курсовая работа по ИИ</center>", unsafe_allow_html=True)