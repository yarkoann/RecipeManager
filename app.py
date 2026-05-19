import streamlit as st
import json
import re
import os
from typing import List, Dict, Optional

from diet_analyzer import (diet_analyzer, analyze_diet_compatibility,
                           DishContextClassifier, AdaptationFeasibilityChecker)


# ─────────────────────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

# Объём банок (г) для различных продуктов
CAN_GRAMS: Dict[str, int] = {
    "горох":     400,
    "фасоль":    400,
    "кукуруза":  340,
    "нут":       400,
    "чечевица":  400,
    "томаты":    400,
    "огурцы":    400,
    "грибы":     400,
    "оливки":    300,
    "тунец":     185,
    "сардины":   185,
}


def can_to_grams(product_name: str, cans: float) -> float:
    """Конвертирует банки в граммы по таблице стандартных объёмов."""
    grams_per_can = CAN_GRAMS.get(product_name.lower(), 400)
    return cans * grams_per_can


def load_css():
    css_file = "static/css/style.css"
    if os.path.exists(css_file):
        with open(css_file, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  RecipeManager
# ─────────────────────────────────────────────────────────────────────────────

class RecipeManager:
    """Управление базой рецептов."""

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

    def get_ingredient_info(self, name):
        return next((i for i in self.ingredients if i["name"] == name), None)

    def find_substitutions(self, ingredient, reason=None):
        """Ищет замены с учётом условий."""
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
#  RecipeAdapter
# ─────────────────────────────────────────────────────────────────────────────

class RecipeAdapter:
    """Адаптация рецептов под продукты, аллергии и диету пользователя."""

    def __init__(self):
        self.manager = RecipeManager()
        self.substitution_confidence: Dict[str, float] = {}

    # ── Парсинг продуктов ────────────────────────────────────────────────────

    def parse_user_products(self, text: str) -> List[dict]:
        """Парсит строку продуктов пользователя."""
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

    # ── Оценка уверенности в замене ──────────────────────────────────────────

    def _check_substitution_confidence(self, substitution: dict, ingredient: dict,
                                       dish_context: dict = None) -> float:
        """
        ИИ: многофакторная оценка уверенности в замене.
        Учитывает контекст блюда для яиц и других «контекстных» ингредиентов.
        """
        confidence = 0.8

        # Бонус за контекстную замену яиц
        if dish_context and "яйц" in ingredient.get('name', ''):
            egg_role = dish_context.get('egg_role', 'general')
            sub_alt = substitution.get('alternative', '')
            # Лучшие замены для выпечки
            if egg_role == 'leavening' and 'льняная' in sub_alt:
                confidence += 0.12
            # Лучшие замены для салатов
            elif egg_role == 'garnish' and 'тофу' in sub_alt:
                confidence += 0.10
            # Хуже, если банан предлагается для несладкого блюда
            elif egg_role == 'garnish' and 'банан' in sub_alt:
                confidence -= 0.20

        # Бонус за детальную инструкцию
        if substitution.get('note') and len(substitution['note']) > 20:
            confidence += 0.05

        # Бонус за точный коэффициент замены
        if substitution.get('ratio') and substitution['ratio'] != 1.0:
            confidence += 0.03

        key = f"{ingredient.get('name', '')}->{substitution.get('alternative', '')}"
        self.substitution_confidence[key] = round(min(confidence, 1.0), 2)
        return self.substitution_confidence[key]

    # ── Применение замены ─────────────────────────────────────────────────────

    def _apply_substitution(self, ingredients: list, original_ing: dict,
                             substitution: dict, scale_factor: float):
        """Применяет замену ингредиента в итоговом списке."""
        if original_ing.get('by_taste', False):
            scale_factor = 1.0
            quantity_value = 0
        else:
            quantity_value = original_ing.get('quantity', 0) or 0

        # Полная таблица единиц для альтернативных продуктов
        unit_mapping = {
            # Жидкости → мл
            'молоко': 'мл', 'вода': 'мл', 'масло растительное': 'мл',
            'соевое молоко': 'мл', 'миндальное молоко': 'мл',
            'кокосовое молоко': 'мл', 'кефир': 'мл', 'сливки': 'мл',
            'кокосовые сливки': 'мл', 'растительное молоко': 'мл', 'аквафаба': 'мл',
            # Сыпучие → г
            'мука': 'г', 'рисовая мука': 'г', 'миндальная мука': 'г',
            'кокосовая мука': 'г', 'нутовая мука': 'г', 'гречневая мука': 'г',
            'кукурузная мука': 'г', 'крахмал': 'г', 'крахмал + вода': 'г',
            'сахар': 'г', 'соль': 'г', 'стевия': 'г', 'эритрит': 'г',
            'какао': 'г', 'агар-агар': 'г',
            # Бобовые → г (банки конвертированы ранее)
            'горох': 'г', 'фасоль': 'г', 'кукуруза': 'г',
            'нут отварной': 'г', 'чечевица': 'г',
            # Твёрдые продукты → г
            'тофу': 'г', 'тофу (мягкий)': 'г', 'тофу (плотный)': 'г',
            'творог': 'г', 'сыр': 'г', 'сметана': 'г', 'йогурт': 'г',
            'творожный сыр': 'г', 'рикотта': 'г', 'маскарпоне': 'г',
            'цветная капуста': 'г', 'брокколи': 'г', 'кабачок': 'г',
            'грибы': 'г', 'авокадо': 'г', 'банан (пюре)': 'г',
            'мясо': 'г', 'курица': 'г', 'сейтан': 'г',
            'веганский сыр': 'г', 'веганский майонез': 'г',
            'запечённая курица или говядина': 'г',
            'греческий йогурт + горчица': 'г',
            'сметана + горчица': 'г',
            'томатная паста + вода + специи': 'г',
            'кокосовый амино соус': 'мл', 'тамари': 'мл',
            'сироп агавы': 'мл', 'кленовый сироп': 'мл',
            # Штучные
            'яйца': 'шт', 'лимон': 'шт', 'банан': 'шт',
        }

        # Ключевые слова для автоопределения единицы по имени альтернативы
        def _detect_unit(name: str) -> str:
            n = name.lower()
            if any(k in n for k in ['мука', 'крахмал', 'порошок', 'сахар', 'соль',
                                     'творог', 'сыр', 'тофу', 'капуста', 'брокколи',
                                     'кабачок', 'грибы', 'мясо', 'курица', 'сейтан',
                                     'нут', 'фасоль', 'горох', 'чечевица', 'авокадо',
                                     'кукуруза', 'агар', 'эритрит', 'стевия', 'какао',
                                     'пюре', 'паста', 'горчица']):
                return 'г'
            if any(k in n for k in ['молоко', 'сливки', 'кефир', 'сок', 'вода',
                                     'масло', 'соус', 'сироп', 'аквафаба']):
                return 'мл'
            if any(k in n for k in ['яйц', 'лимон', 'банан', 'яблок']):
                return 'шт'
            return None  # не удалось определить

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
            if detected:
                new_unit = detected
            else:
                # Наследуем единицу оригинала, но банку → г
                orig_unit = original_ing.get('unit', 'шт')
                new_unit = 'г' if orig_unit == 'банка' else orig_unit

        ratio = substitution.get('ratio', 1.0)

        # Конвертация банок → граммы
        if original_ing.get('unit') == 'банка':
            original_quantity_grams = can_to_grams(
                original_ing.get('name', ''), quantity_value
            )
            new_quantity = original_quantity_grams * scale_factor * ratio
            new_unit = 'г'
        else:
            new_quantity = quantity_value * scale_factor * ratio

        # Специальная обработка
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
            substitute = {
                'name': alt_name,
                'quantity': None, 'unit': '',
                'is_substitute': True,
                'original_name': ing_name,
                'by_taste': True,
            }
        else:
            substitute = {
                'name': alt_name,
                'quantity': round(new_quantity, 1),
                'unit': new_unit,
                'is_substitute': True,
                'original_name': ing_name,
            }

        for i, ing in enumerate(ingredients):
            if ing.get('name') == ing_name:
                ingredients[i] = substitute
                break

    # ── Расчёт порций ────────────────────────────────────────────────────────

    def _calculate_servings(self, ingredients: list, manual_servings=None) -> int:
        """ИИ: расчёт количества порций на основе суммарного веса."""
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

    # ── Нормализация имён ────────────────────────────────────────────────────

    def normalize_ingredient_name(self, name: str) -> str:
        name_lower = name.lower().strip()
        synonyms = {
            "горошек": "горох", "консервированный горох": "горох",
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
        }
        if name_lower in synonyms:
            return synonyms[name_lower]
        for key, value in synonyms.items():
            if key in name_lower:
                return value
        return name_lower

    # ── Аллергены ────────────────────────────────────────────────────────────

    def _expand_allergies(self, allergies: list) -> list:
        """
        ИИ: расширяет список аллергий — синонимы и группы.
        Покрывает 14 главных аллергенов ЕС + распространённые русскоязычные формы.
        """
        # Словарь синонимов: что пишет пользователь → что искать в базе
        ALLERGEN_GROUPS = {
            # Молочные
            'молоко':          ['молоко', 'лактоза'],
            'молочка':         ['молоко', 'лактоза'],
            'молочные':        ['молоко', 'лактоза'],
            'молочные продукты':['молоко', 'лактоза'],
            'лактоза':         ['лактоза', 'молоко'],
            'казеин':          ['молоко', 'лактоза'],
            # Яйца
            'яйца':            ['яйца'],
            'яйцо':            ['яйца'],
            'белок яйца':      ['яйца'],
            'желток':          ['яйца'],
            # Глютен / злаки
            'глютен':          ['глютен', 'пшеница'],
            'пшеница':         ['глютен', 'пшеница'],
            'злаки':           ['глютен', 'пшеница', 'овёс'],
            'рожь':            ['глютен'],
            'ячмень':          ['глютен'],
            'овёс':            ['глютен', 'овёс'],
            # Орехи
            'орехи':           ['орехи', 'миндаль', 'фундук', 'грецкие орехи', 'кешью'],
            'древесные орехи': ['орехи', 'миндаль', 'фундук', 'грецкие орехи', 'кешью'],
            'миндаль':         ['орехи', 'миндаль'],
            'фундук':          ['орехи', 'фундук'],
            'грецкие орехи':   ['орехи', 'грецкие орехи'],
            'кешью':           ['орехи', 'кешью'],
            'кедровые орехи':  ['орехи'],
            'бразильский орех':['орехи'],
            'фисташки':        ['орехи'],
            'макадамия':       ['орехи'],
            # Арахис (отдельно от орехов)
            'арахис':          ['арахис'],
            'арахисовое масло':['арахис'],
            'арахисовая паста':['арахис'],
            # Соя
            'соя':             ['соя'],
            'соевые':          ['соя'],
            'соевый':          ['соя'],
            # Рыба
            'рыба':            ['рыба'],
            'рыбный':          ['рыба'],
            'тунец':           ['рыба'],
            'лосось':          ['рыба'],
            'треска':          ['рыба'],
            # Морепродукты
            'ракообразные':    ['ракообразные', 'морепродукты'],
            'морепродукты':    ['ракообразные', 'моллюски', 'морепродукты'],
            'креветки':        ['ракообразные', 'морепродукты'],
            'краб':            ['ракообразные', 'морепродукты'],
            'омар':            ['ракообразные', 'морепродукты'],
            'моллюски':        ['моллюски', 'морепродукты'],
            'мидии':           ['моллюски', 'морепродукты'],
            'устрицы':         ['моллюски', 'морепродукты'],
            'кальмар':         ['моллюски', 'морепродукты'],
            # Кунжут
            'кунжут':          ['кунжут'],
            'кунжутное масло': ['кунжут'],
            'тахини':          ['кунжут'],
            # Горчица
            'горчица':         ['горчица'],
            # Сельдерей
            'сельдерей':       ['сельдерей'],
            # Люпин
            'люпин':           ['люпин'],
            # Диоксид серы / сульфиты
            'сульфиты':        ['диоксид серы', 'сульфиты'],
            'диоксид серы':    ['диоксид серы', 'сульфиты'],
            'е220':            ['диоксид серы', 'сульфиты'],
        }

        expanded = []
        for a in allergies:
            a_l = a.lower().strip()
            if a_l in ALLERGEN_GROUPS:
                expanded.extend(ALLERGEN_GROUPS[a_l])
            else:
                expanded.append(a_l)
        return list(set(expanded))

    # ── Главный метод адаптации ───────────────────────────────────────────────

    def adapt_recipe(self, recipe: dict, user_products_text: str,
                     allergies=None, diet=None) -> dict:
        """
        Адаптирует рецепт под наличие продуктов, аллергии и диету.
        Поддерживает контекстные замены (тип блюда учитывается).
        """
        has_user_products = bool(user_products_text and user_products_text.strip())

        if has_user_products:
            user_products = self.parse_user_products(user_products_text)
            user_dict = {p['name']: p for p in user_products}
        else:
            user_dict = {}

        recipe_ingredients = recipe['ingredients'].copy()
        processed_allergies = self._expand_allergies(allergies or [])

        # Определяем контекст блюда (имя + категория)
        dish_context = DishContextClassifier.classify(
            recipe.get('name', ''), recipe.get('category', '')
        )

        # ── Расчёт масштаба ──────────────────────────────────────────────────
        scale_factor = 1.0

        if has_user_products:
            # Сначала уменьшение (лимитирующий продукт)
            min_scale = 1.0
            for ing in recipe_ingredients:
                if ing.get('by_taste') or ing.get('quantity') is None:
                    continue
                if ing['name'] in user_dict:
                    uq = user_dict[ing['name']]['quantity']
                    if uq is not None and uq > 0 and uq < ing['quantity']:
                        min_scale = min(min_scale, uq / ing['quantity'])
            scale_factor = min_scale

            # Затем увеличение (избыток)
            max_scale = scale_factor
            for ing in recipe_ingredients:
                if ing.get('by_taste') or ing.get('quantity') is None:
                    continue
                if ing['name'] in user_dict:
                    uq = user_dict[ing['name']]['quantity']
                    if uq is not None and uq > 0 and uq > ing['quantity'] * scale_factor:
                        max_scale = max(max_scale, uq / ing['quantity'])
            scale_factor = max_scale

        # ── Масштабирование ингредиентов ─────────────────────────────────────
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
                        excess_info.append({
                            'name': ing['name'],
                            'recipe_needs': round(new_quantity, 1),
                            'user_has': uq,
                            'excess': round(uq - new_quantity, 1),
                            'unit': ing['unit']
                        })
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1)})
                    available.append(ing)
                else:
                    scaled_ingredients.append({
                        **ing,
                        'quantity': uq,
                        'limited': True,
                        'original_quantity': round(new_quantity, 1)
                    })
                    short.append({**ing, 'user_quantity': uq, 'shortage': ing['quantity'] - uq})
            else:
                if has_user_products:
                    scaled_ingredients.append({**ing, 'quantity': round(new_quantity, 1), 'missing': True})
                    missing.append(ing)
                else:
                    scaled_ingredients.append({**ing, 'quantity': round(ing['quantity'], 1)})
                    available.append(ing)

        # ── Диета ────────────────────────────────────────────────────────────
        diet_issues = []
        if diet and diet != "Нет":
            for ing in recipe_ingredients:
                compatible, _, _ = diet_analyzer.check_compatibility(
                    ing, diet, dish_context=dish_context
                )
                if not compatible and not any(d['name'] == ing['name'] for d in diet_issues):
                    diet_issues.append({**ing, 'diet': diet})

        # ── Аллергии ─────────────────────────────────────────────────────────
        problem_allergies = []
        if processed_allergies:
            for ing in recipe_ingredients:
                ing_info = self.manager.get_ingredient_info(ing['name'])
                if ing_info and ing_info.get('allergens'):
                    for allergen in processed_allergies:
                        if allergen.lower() in [a.lower() for a in ing_info['allergens']]:
                            if not any(pa['name'] == ing['name'] for pa in problem_allergies):
                                problem_allergies.append({**ing, 'allergen': allergen, 'info': ing_info})

        # ── Сбор проблем ─────────────────────────────────────────────────────
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

        # ── Подбор замен ─────────────────────────────────────────────────────
        substitutions_made = []
        alternatives_for_display = []

        for key, issue_data in issues_to_resolve.items():
            ing = issue_data['ingredient']
            reasons = issue_data['reasons']

            search_reason = None
            if any('allergy_' in r for r in reasons):
                search_reason = next(
                    (r.replace('allergy_', '') for r in reasons if r.startswith('allergy_')), None
                )
            elif any('diet_' in r for r in reasons):
                search_reason = diet

            # Контекстные замены из DietAnalyzer (для яиц и т.д.)
            context_alts = diet_analyzer.find_alternatives(
                ing['name'], search_reason, dish_context=dish_context
            )

            # Стандартные замены из базы
            db_subs = self.manager.find_substitutions(ing['name'], search_reason)

            ingredient_alternatives = []
            best_sub = None
            best_confidence = 0.0

            # Сначала контекстные замены
            for alt in context_alts:
                fake_sub = {
                    'ingredient': ing['name'],
                    'alternative': alt['name'],
                    'ratio': alt.get('ratio', 1.0),
                    'note': alt.get('description', ''),
                    'condition': search_reason or 'всегда'
                }
                conf = self._check_substitution_confidence(fake_sub, ing, dish_context)
                ingredient_alternatives.append({
                    'name': alt['name'],
                    'ratio': alt.get('ratio', 1.0),
                    'note': alt.get('description', ''),
                    'confidence': conf,
                    'condition': search_reason or 'всегда'
                })
                if conf > best_confidence:
                    best_confidence = conf
                    best_sub = fake_sub

            # Затем базовые замены
            for sub in db_subs:
                conf = self._check_substitution_confidence(sub, ing, dish_context)
                alt_name = sub['alternative']
                if not any(a['name'] == alt_name for a in ingredient_alternatives):
                    ingredient_alternatives.append({
                        'name': alt_name,
                        'ratio': sub.get('ratio', 1.0),
                        'note': sub.get('note', ''),
                        'confidence': conf,
                        'condition': sub.get('condition', 'всегда')
                    })
                    if conf > best_confidence:
                        best_confidence = conf
                        best_sub = sub

            if ingredient_alternatives:
                alternatives_for_display.append({
                    'original': ing['name'],
                    'alternatives': sorted(
                        ingredient_alternatives, key=lambda x: x['confidence'], reverse=True
                    )
                })

            if best_sub and best_confidence > 0.5:
                reason_text = []
                for r in reasons:
                    if r.startswith('allergy_'):
                        reason_text.append(f"аллергия на {r.replace('allergy_', '')}")
                    elif r.startswith('diet_'):
                        reason_text.append(f"диета {diet}")
                    elif r == 'explicitly_missing':
                        reason_text.append("указано с 0")

                substitutions_made.append({
                    'original': ing['name'],
                    'alternative': best_sub.get('alternative', best_sub.get('name', '')),
                    'reason': ", ".join(reason_text),
                    'note': best_sub.get('note', best_sub.get('description', '')),
                    'confidence': best_confidence,
                    'ratio': best_sub.get('ratio', 1.0)
                })
                self._apply_substitution(scaled_ingredients, ing, best_sub, scale_factor)

        manual_servings = recipe.get('servings')
        servings = self._calculate_servings(scaled_ingredients, manual_servings)

        # Оценка возможности адаптации
        issues_for_check = []
        for ing in diet_issues + problem_allergies:
            best = next((s for s in substitutions_made if s['original'] == ing['name']), None)
            issues_for_check.append({
                'name': ing['name'],
                'best_sub_name': best['alternative'] if best else '',
            })
        feasibility = AdaptationFeasibilityChecker.check(recipe, issues_for_check, dish_context)

        return {
            'recipe_name': recipe['name'],
            'ingredients': scaled_ingredients,
            'missing': missing,
            'explicitly_missing': explicitly_missing,
            'short': short,
            'available': available,
            'excess': excess_info,
            'diet_issues': diet_issues,
            'allergy_issues': problem_allergies,
            'substitutions': substitutions_made,
            'alternatives': alternatives_for_display,
            'scale_factor': scale_factor,
            'steps': recipe.get('steps', []),
            'servings': servings,
            'dish_context': dish_context,
            'feasibility': feasibility,
        }

    # ── Вспомогательные ─────────────────────────────────────────────────────

    def _parse_recipe_text(self, text: str) -> list:
        """Парсит список ингредиентов из текста."""
        ingredients = []
        taste_phrases = ['по вкусу', 'по желанию', 'опционально', 'по необходимости']
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            is_by_taste = any(p in line.lower() for p in taste_phrases)
            match = re.search(
                r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*'
                r'(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?',
                line
            )
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
#  Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

adapter = RecipeAdapter()

st.set_page_config(page_title="Умный адаптер рецептов", page_icon="🍳", layout="wide")
load_css()

st.markdown('<h1 class="main-header">Умный адаптер рецептов</h1>', unsafe_allow_html=True)

with st.sidebar:
    with st.expander("Как это работает", expanded=False):
        st.markdown("""
        1. **Выбери рецепт** из базы
        2. **Укажи продукты**, которые есть (формат: название количество единица)
        3. **Добавь аллергии** и выбери диету
        4. **Получи адаптированный рецепт** с заменами!

        **Совет:** Если оставить поле продуктов пустым — считается, что всё есть.
        """)

    with st.expander("Где используется ИИ", expanded=False):
        st.write("• Контекстный анализ типа блюда (выпечка/салат/горячее)")
        st.write("• Умные замены яиц с учётом роли в рецепте")
        st.write("• Оценка уверенности в замене (многофакторная)")
        st.write("• Расчёт оптимальных пропорций")
        st.write("• Точная конвертация банок в граммы")
        st.write("• Расчёт количества порций")

    with st.expander("Управление базой данных", expanded=False):
        if st.button("Восстановить базовые рецепты"):
            default_recipes = {
                "recipes": [
                    {
                        "id": 1, "name": "Шоколадный торт", "category": "десерты",
                        "ingredients": [
                            {"name": "мука", "quantity": 300, "unit": "г"},
                            {"name": "яйца", "quantity": 3, "unit": "шт"},
                            {"name": "молоко", "quantity": 200, "unit": "мл"},
                            {"name": "сахар", "quantity": 150, "unit": "г"},
                            {"name": "масло сливочное", "quantity": 100, "unit": "г"},
                            {"name": "разрыхлитель", "quantity": 10, "unit": "г"},
                            {"name": "какао", "quantity": 50, "unit": "г"}
                        ],
                        "steps": [
                            "Смешать сухие ингредиенты",
                            "Добавить яйца и молоко",
                            "Выпекать 30 мин при 180°C"
                        ],
                        "time": 60, "difficulty": "средняя"
                    },
                    {
                        "id": 2, "name": "Блины", "category": "завтраки",
                        "ingredients": [
                            {"name": "мука", "quantity": 200, "unit": "г"},
                            {"name": "молоко", "quantity": 500, "unit": "мл"},
                            {"name": "яйца", "quantity": 2, "unit": "шт"},
                            {"name": "сахар", "quantity": 20, "unit": "г"},
                            {"name": "масло растительное", "quantity": 30, "unit": "мл"},
                            {"name": "соль", "quantity": 2, "unit": "г"}
                        ],
                        "steps": ["Смешать все ингредиенты", "Жарить на сковороде"],
                        "time": 30, "difficulty": "легкая"
                    },
                    {
                        "id": 3, "name": "Сырники", "category": "завтраки",
                        "ingredients": [
                            {"name": "творог", "quantity": 500, "unit": "г"},
                            {"name": "яйца", "quantity": 1, "unit": "шт"},
                            {"name": "мука", "quantity": 100, "unit": "г"},
                            {"name": "сахар", "quantity": 50, "unit": "г"},
                            {"name": "соль", "quantity": 1, "unit": "г"}
                        ],
                        "steps": ["Смешать творог с яйцом", "Добавить муку и сахар",
                                  "Обжарить на сковороде"],
                        "time": 40, "difficulty": "легкая"
                    },
                    {
                        "id": 4, "name": "Салат \"Оливье\"", "category": "салаты",
                        "ingredients": [
                            {"name": "картофель", "quantity": 400.0, "unit": "г"},
                            {"name": "яйца", "quantity": 6.0, "unit": "шт"},
                            {"name": "огурцы соленые", "quantity": 300.0, "unit": "г"},
                            {"name": "колбаса", "quantity": 300.0, "unit": "г"},
                            {"name": "майонез", "quantity": 300.0, "unit": "мл"},
                            {"name": "горох", "quantity": 1.0, "unit": "банка"}
                        ],
                        "steps": [
                            "Отварить яйца и картофель",
                            "Нарезать кубиком картофель, яйца, огурцы и колбасу",
                            "Смешать все ингредиенты в миске, заправить майонезом"
                        ],
                        "time": 30, "difficulty": "легкая"
                    },
                    {
                        "id": 5, "name": "Омлет с помидором", "category": "завтраки",
                        "ingredients": [
                            {"name": "яйца", "quantity": 2.0, "unit": "шт", "by_taste": False},
                            {"name": "помидор", "quantity": 1.0, "unit": "шт", "by_taste": False},
                            {"name": "соль", "quantity": None, "unit": "", "by_taste": True},
                            {"name": "майонез", "quantity": None, "unit": "", "by_taste": True}
                        ],
                        "steps": [
                            "Промыть и нарезать помидор",
                            "Взбить яйца с солью",
                            "Жарить яйца вместе с помидором до готовности"
                        ],
                        "time": 5, "difficulty": "легкая", "servings": 1
                    }
                ]
            }
            with open("data/recipes.json", 'w', encoding='utf-8') as f:
                json.dump(default_recipes, f, ensure_ascii=False, indent=2)
            st.success("Базовые рецепты восстановлены!")
            st.rerun()

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0

tab1, tab2 = st.tabs(["Выбрать из базы", "Добавить рецепт"])

# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 1: Выбор рецепта
# ─────────────────────────────────────────────────────────────────────────────

with tab1:
    st.header("Выбери рецепт из базы")
    col1, col2 = st.columns([1, 1])

    with col1:
        search_query = st.text_input("Поиск по названию", key="search")
        all_recipes = adapter.manager.get_all_recipes()

        if search_query:
            filtered_recipes = [r for r in all_recipes if search_query.lower() in r['name'].lower()]
        else:
            categories = sorted(set(r.get('category', 'другие') for r in all_recipes))
            selected_category = st.selectbox("Категория", ["Все"] + categories)
            if selected_category == "Все":
                filtered_recipes = all_recipes
            else:
                filtered_recipes = [r for r in all_recipes if r.get('category') == selected_category]

    with col2:
        if filtered_recipes:
            recipe_names = [r['name'] for r in filtered_recipes]
            selected_name = st.selectbox("Выбери рецепт", recipe_names)
            selected_recipe = next(r for r in filtered_recipes if r['name'] == selected_name)

            # Показываем тип блюда
            ctx = DishContextClassifier.classify(
                selected_recipe.get('name', ''), selected_recipe.get('category', '')
            )
            dish_type_label = []
            if ctx['is_sweet']:
                dish_type_label.append("🍰 Выпечка/Десерт")
            if ctx['is_savory']:
                dish_type_label.append("🥗 Несладкое блюдо")
            if dish_type_label:
                st.caption("Тип блюда: " + " | ".join(dish_type_label))

            st.markdown("### Ингредиенты:")
            for ing in selected_recipe['ingredients']:
                if ing.get('by_taste', False):
                    st.markdown(f"• {ing['name']} (по вкусу)")
                elif ing.get('unit') == 'банка':
                    grams = can_to_grams(ing['name'], ing['quantity'])
                    st.markdown(
                        f"• {ing['name']}: {ing['quantity']} банка "
                        f"(≈ {int(grams)} г)"
                    )
                else:
                    st.markdown(f"• {ing['name']}: {ing['quantity']}{ing['unit']}")
        else:
            st.warning("Рецепты не найдены")

    if filtered_recipes and 'selected_recipe' in locals():
        st.markdown("---")
        st.subheader("Какие продукты у тебя есть?")

        user_products = st.text_area(
            "Введи продукты через запятую",
            placeholder="мука 500г, яйца 3 шт, молоко 200мл, горох 1 банка, разрыхлитель 0г",
            key="products_tab1",
            height=80,
            help="Формат: продукт количество единица\n"
                 "Оставь пустым — считается, что всё есть\n"
                 "Если продукта нет — укажи 0 (например: яйца 0 шт)"
        )

        col1, col2 = st.columns(2)
        with col1:
            allergies_input = st.text_input(
                "Аллергии (через запятую)",
                placeholder="лактоза, глютен, яйца",
                help="При указании 'молоко' автоматически добавляется лактоза"
            )
        with col2:
            diet = st.selectbox(
                "Диета",
                ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"],
                key="diet_tab1"
            )

        if st.button("Адаптировать", type="primary", use_container_width=True):
            if user_products or allergies_input or diet != "Нет":
                allergies = [a.strip().lower() for a in allergies_input.split(',') if a.strip()] \
                    if allergies_input else []

                with st.spinner("ИИ анализирует рецепт..."):
                    result = adapter.adapt_recipe(
                        selected_recipe,
                        user_products or "",
                        allergies,
                        diet
                    )

                st.markdown("---")
                st.markdown(f"## {result['recipe_name']}")

                # ── Контекст блюда ───────────────────────────────────────────
                dctx = result.get('dish_context', {})
                if dctx.get('egg_role') and dctx['egg_role'] != 'general':
                    label = DishContextClassifier.egg_role_label(dctx['egg_role'])
                    if label:
                        st.info(label)

                # ── Оценка возможности адаптации ─────────────────────────────
                feas = result.get('feasibility', {})

                # Невозможные замены — показываем красным + альтернативные блюда
                if feas.get('impossible_reasons'):
                    st.error("**Адаптация частично невозможна:**")
                    for reason in feas['impossible_reasons']:
                        st.error(reason)
                    if feas.get('alternative_dishes'):
                        st.markdown("### 🍽️ Рекомендуемые альтернативные блюда:")
                        for alt in feas['alternative_dishes']:
                            st.success(f"**{alt['name']}** — {alt['note']}")

                # Предупреждения о сложной адаптации
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

                if result['excess']:
                    with st.expander("Обнаружен избыток продуктов — рецепт увеличен"):
                        for e in result['excess']:
                            st.write(
                                f"• {e['name']}: нужно {e['recipe_needs']}{e['unit']}, "
                                f"у вас {e['user_has']}{e['unit']} "
                                f"(останется {e['excess']}{e['unit']})"
                            )

                if result['short']:
                    with st.expander("Продуктов меньше нормы"):
                        for s in result['short']:
                            st.write(
                                f"• {s['name']}: нужно {s['quantity']}{s['unit']}, "
                                f"есть {s['user_quantity']}{s['unit']}"
                            )
                        st.info("💡 Если продукта нет совсем — укажи его с 0")

                if result['allergy_issues']:
                    with st.expander("Аллергены в рецепте"):
                        for a in result['allergy_issues']:
                            st.write(f"• {a['name']} содержит аллерген: {a['allergen']}")

                if result['diet_issues']:
                    with st.expander("Проблемы с диетой"):
                        for d in result['diet_issues']:
                            st.write(f"• {d['name']} не соответствует диете {d['diet']}")

                if result['substitutions']:
                    with st.expander("Произведённые замены"):
                        for sub in result['substitutions']:
                            st.write(f"• **{sub['original']}** → **{sub['alternative']}**")
                            st.caption(f"  Причина: {sub['reason']}")
                            if sub['note']:
                                st.caption(f"  ⓘ {sub['note']}")

                if result.get('alternatives'):
                    with st.expander("Другие доступные альтернативы"):
                        for alt_group in result['alternatives']:
                            if len(alt_group['alternatives']) > 1:
                                st.markdown(f"**{alt_group['original']}** → можно заменить на:")
                                for alt in alt_group['alternatives']:
                                    is_selected = any(
                                        s['original'] == alt_group['original']
                                        and s['alternative'] == alt['name']
                                        for s in result['substitutions']
                                    )
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
                        else:
                            st.markdown(f"**{ing['name']}**")
                    with c2:
                        if ing.get('by_taste'):
                            st.markdown("по вкусу")
                        else:
                            # Отображаем банки с граммами
                            if ing.get('unit') == 'банка':
                                grams = can_to_grams(ing.get('name', ''), ing['quantity'])
                                st.markdown(f"{ing['quantity']} банка (≈{int(grams)}г)")
                            else:
                                st.markdown(f"{ing['quantity']}{ing['unit']}")
                    with c3:
                        if ing.get('original_name'):
                            st.caption(f"замена {ing['original_name']}")
                        elif ing.get('limited'):
                            st.caption(f"нужно {ing['original_quantity']}{ing['unit']}")

                if result['steps']:
                    with st.expander("Шаги приготовления"):
                        for i, step in enumerate(result['steps'], 1):
                            st.write(f"{i}. {step}")
            else:
                st.error("Введи продукты или укажи диету/аллергию")

# ─────────────────────────────────────────────────────────────────────────────
#  Вкладка 2: Добавить рецепт
# ─────────────────────────────────────────────────────────────────────────────

with tab2:
    st.header("Добавить новый рецепт")

    with st.form("add_recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("Название рецепта")
        with col2:
            servings_manual = st.number_input(
                "Количество порций", min_value=1, value=1,
                help="На сколько персон рассчитан рецепт"
            )

        category = st.selectbox(
            "Категория",
            ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"]
        )

        # Предпросмотр контекста блюда
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
        steps_text = st.text_area(
            "Каждый шаг с новой строки",
            placeholder="Смешать сухие ингредиенты\nДобавить яйца и молоко\nВыпекать 30 мин",
            height=150
        )

        col1, col2 = st.columns(2)
        with col1:
            time_val = st.number_input("Время приготовления (мин)", min_value=5, value=30)
        with col2:
            difficulty = st.selectbox("Сложность", ["легкая", "средняя", "сложная"])

        submitted = st.form_submit_button("Сохранить", type="primary", use_container_width=True)

        if submitted:
            if recipe_name and ingredients_text:
                existing_names = [r['name'].lower() for r in adapter.manager.get_all_recipes()]
                if recipe_name.lower() in existing_names:
                    st.error(f"Рецепт '{recipe_name}' уже существует в базе!")
                else:
                    ingredients = []
                    taste_phrases = ['по вкусу', 'по желанию', 'опционально', 'по необходимости']
                    invalid_lines = []

                    for line in ingredients_text.strip().split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        if ',' in line:
                            line = line.replace(',', '')
                        is_by_taste = any(p in line.lower() for p in taste_phrases)
                        match = re.search(
                            r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*'
                            r'(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?',
                            line
                        )
                        if match:
                            name = adapter.normalize_ingredient_name(
                                match.group(1).strip().lower()
                            )
                            qty = float(match.group(2).replace(',', '.'))
                            unit = match.group(3) or 'шт'
                            if unit in ['банка', 'банки', 'банок', 'б']:
                                unit = 'банка'
                            ingredients.append({
                                'name': name, 'quantity': qty, 'unit': unit, 'by_taste': False
                            })
                        elif is_by_taste:
                            clean = line.lower()
                            for p in taste_phrases:
                                clean = clean.replace(p, '').strip()
                            name = adapter.normalize_ingredient_name(clean or line.lower())
                            ingredients.append({
                                'name': name, 'quantity': None, 'unit': '', 'by_taste': True
                            })
                        else:
                            invalid_lines.append(line)

                    if invalid_lines:
                        st.warning(f"Не удалось распознать: {', '.join(invalid_lines)}")

                    steps = [s.strip() for s in steps_text.strip().split('\n') if s.strip()]

                    if ingredients:
                        new_recipe = {
                            'name': recipe_name, 'category': category,
                            'ingredients': ingredients, 'steps': steps,
                            'time': time_val, 'difficulty': difficulty,
                            'servings': servings_manual
                        }
                        recipe_id = adapter.manager.add_recipe(new_recipe)
                        if recipe_id:
                            st.success(f"Рецепт '{recipe_name}' успешно добавлен!")
                            st.rerun()
                        else:
                            st.error("Ошибка при добавлении рецепта!")
                    else:
                        st.error("Не удалось распознать ингредиенты! Проверьте формат.")
            else:
                st.error("Заполните название и ингредиенты!")

st.markdown("---")
st.markdown(
    "<center>Умный адаптер рецептов — курсовая работа по ИИ</center>",
    unsafe_allow_html=True
)