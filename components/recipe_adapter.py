
#RecipeAdapter — центральный компонент адаптации рецептов.
#Координирует парсинг, масштабирование, замены и оценку уверенности.

import re
from typing import List, Dict

from components.recipe_manager import RecipeManager, can_to_grams
from components.diet_analyzer import (
    DietAnalyzer, DishContextClassifier, AdaptationFeasibilityChecker, diet_analyzer,
)


class RecipeAdapter:
    def __init__(self):
        self.manager = RecipeManager()
        self.substitution_confidence: Dict[str, float] = {}

    # Синонимы и нормализация

    SYNONYM_MAP = {


        "горошек": "горох",
        "консервированный горох": "горох",
        "консервированный горошек": "горох",
        "горох консервированный": "горох",
        "горошек консервированный": "горох",
        "горох в банке": "горох",
        "консервированная фасоль": "фасоль",
        "консервированный нут": "нут",
        "консервированная кукуруза": "кукуруза",
        "сладкая кукуруза": "кукуруза",
        # молочные
        "коровье молоко": "молоко",
        "домашнее молоко": "молоко",
        "сливочное маслице": "масло сливочное",
        "сливочное масло": "масло сливочное",
        # курица

        "курица": "курица",
        "куриное филе": "курица",
        "куриная грудка": "курица",
        "куриное бедро": "курица",
        "филе куриное": "курица",
        "грудка куриная": "курица",
        "бедро куриное": "курица",
        "куриные бедра": "курица",
        # мясо
        "свинина": "мясо",
        "говядина": "мясо",
        # перец
        "сладкий перец": "перец сладкий",
        "болгарский перец": "перец болгарский",
        "острый перец": "перец острый",
        # растительное масло
        "растительное масло": "масло растительное",
        # прочее
        "греческий йогурт": "греческий йогурт",
        "маринованные огурцы": "огурцы соленые",
        # СЫРЫ и сырные продукты
        "сыр": "сыр",
        "пармезан": "сыр",
        "моцарелла": "сыр",
        "чеддер": "сыр",
        "гауда": "сыр",
        "рикотта": "сыр",
        "маскарпоне": "сыр",
        "фета": "сыр",
        "брынза": "сыр",
        "сулугуни": "сыр",

        # ТОМАТЫ / ПОМИДОРЫ
        "помидор": "помидор",
        "томат": "помидор",
        "томаты": "помидор",
        "черри": "помидор",

        # МУКА
        "мука пшеничная": "мука",
        "пшеничная мука": "мука",

        # МАСЛО
        "подсолнечное масло": "масло растительное",
        "оливковое масло": "масло растительное",

        # МОЛОКО
        "коровье молоко": "молоко",
        "цельное молоко": "молоко",

        # КРУПЫ
        "гречневая крупа": "гречка",
        "греча": "гречка",
        "овсяные хлопья": "овсянка",

        # ОВОЩИ
        "картошка": "картофель",
        "картофель": "картофель",
        "болгарский перец": "перец болгарский",
        "сладкий перец": "перец болгарский",
        "лук": "лук репчатый",
        "репчатый лук": "лук репчатый",
        "зелёный лук": "лук зеленый",

        # ФРУКТЫ
        "яблоко": "яблоко",
        "банан": "банан",
        "лимон": "лимон",
    }

    # Группы ингредиентов для поиска
    INGREDIENT_GROUPS = {
        "сыр": ["сыр", "пармезан", "моцарелла", "чеддер", "гауда", "рикотта", "маскарпоне", "фета", "брынза"],
        "помидор": ["помидор", "томат", "томаты", "черри"],
        "мука": ["мука", "мука пшеничная", "пшеничная мука"],
        "масло растительное": ["масло растительное", "подсолнечное масло", "оливковое масло"],
        "молоко": ["молоко", "коровье молоко", "цельное молоко"],
        "картофель": ["картофель", "картошка"],
        "гречка": ["гречка", "гречневая крупа", "греча"],
        "овсянка": ["овсянка", "овсяные хлопья"],
        "лук репчатый": ["лук репчатый", "репчатый лук","лук"],
        "перец болгарский": ["перец болгарский", "болгарский перец", "сладкий перец"],
        "курица": ["курица", "куриное бедро", "куриное филе", "куриная грудка", "бедро куриное", "филе куриное", "грудка куриная"],

    }

    def expand_ingredient_for_search(self, product_name: str) -> list:
        product_lower = product_name.lower().strip()

        # Сначала проверяем, есть ли продукт в группах
        for group_name, members in self.INGREDIENT_GROUPS.items():
            if product_lower in members or product_lower == group_name:
                return members

        # Проверяем через синонимы
        normalized = self.normalize_ingredient_name(product_lower)
        for group_name, members in self.INGREDIENT_GROUPS.items():
            if normalized in members or normalized == group_name:
                return members

        # Если не нашли группу, возвращаем исходное название
        return [product_lower]



    def normalize_ingredient_name(self, name: str) -> str:
        name_lower = name.lower().strip()
        if name_lower in self.SYNONYM_MAP:
            return self.SYNONYM_MAP[name_lower]
        for key, value in self.SYNONYM_MAP.items():
            if key in name_lower:
                return value
        return name_lower



    # ── Аллергены ─────────────────────────────────────────────────────────

    def _expand_allergies(self, allergies: list) -> list:
        ALLERGEN_GROUPS = {
            "молоко": ["лактоза"],
            "молочка": ["лактоза"],
            "молочные продукты": ["лактоза"],
            "лактоза": ["лактоза"],

            "яйца": ["яйца"],
            "яйцо": ["яйца"],

            "глютен": ["глютен"],
            "пшеница": ["глютен"],

            "орехи": ["орехи"],
            "миндаль": ["орехи"],
            "фундук": ["орехи"],
            "грецкие орехи": ["орехи"],
            "кешью": ["орехи"],

            "арахис": ["арахис"],

            "соя": ["соя"],

            "рыба": ["рыба"],

            "морепродукты": ["морепродукты"],
            "ракообразные": ["морепродукты"],
            "моллюски": ["морепродукты"],

            "кунжут": ["кунжут"]
            ,
            "горчица": ["горчица"],

            "сульфиты": ["сульфиты"],
            "диоксид серы": ["сульфиты"],

        #     пасленовые - картошка, томат, баклажан, перец
        }
        expanded = []
        for a in allergies:
            a_l = a.lower().strip()
            expanded.extend(ALLERGEN_GROUPS.get(a_l, [a_l]))
        return list(set(expanded))

    # Парсинг пользовательского ввода

    def parse_user_products(self, text: str) -> List[dict]:
        products = []
        for item in text.split(","):
            item = item.strip()
            if not item:
                continue

            is_zero = re.search(r'0\s*$', item)
            is_canned = any(w in item for w in [
                "консервированный", "консервированная", "консервированное",
                "баночный", "баночная", "банка", "банок",
            ])

            match = re.search(
                r"([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*"
                r"(банка|банки|банок|б|шт|г|мл|ст\.л|ч\.л|кг|л)?",
                item,
            )
            if match:
                name_raw = match.group(1).strip().lower()

                name = self.normalize_ingredient_name(name_raw)
                quantity = float(match.group(2).replace(",", "."))
                unit = match.group(3) or "г"  # если не указано, по умолчанию граммы
                if is_canned and unit == "шт":
                    unit = "банка"
                if unit in ["банка", "банки", "банок", "б"]:
                    unit = "банка"
                products.append({"name": name, "quantity": quantity, "unit": unit})
            else:
                name_raw = item.lower()
                name = self.normalize_ingredient_name(name_raw)
                unit = "банка" if is_canned else "г"  # по умолчанию граммы
                quantity = 0 if is_zero else None
                products.append({"name": name, "quantity": quantity, "unit": unit})
        return products

    def _parse_recipe_text(self, text: str) -> list:
        ingredients = []
        taste_phrases = ["по вкусу", "по желанию", "опционально", "по необходимости"]
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            is_by_taste = any(p in line.lower() for p in taste_phrases)
            match = re.search(
                r"([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?",
                line,
            )
            if match:
                name = self.normalize_ingredient_name(match.group(1).strip().lower())
                qty = float(match.group(2).replace(",", "."))
                unit = match.group(3) or "шт"
                if unit in ["банка", "банки", "банок", "б"]:
                    unit = "банка"
                ingredients.append({"name": name, "quantity": qty, "unit": unit, "by_taste": False})
            else:
                clean = line.lower()
                for p in taste_phrases:
                    clean = clean.replace(p, "").strip()
                name = self.normalize_ingredient_name(clean or line.lower())
                ingredients.append({"name": name, "quantity": None, "unit": "", "by_taste": True})
        return ingredients

    # ── Оценка уверенности замены ─────────────────────────────────────────

    def _check_substitution_confidence(self, substitution, ingredient, dish_context=None):
        #базовый
        confidence = 0.8

        # для яиц и типа блюда
        if dish_context and "яйц" in ingredient.get("name", ""):
            egg_role = dish_context.get("egg_role", "general")
            sub_alt = substitution.get("alternative", "")
            if egg_role == "leavening" and "льняная" in sub_alt:
                confidence += 0.12
            elif egg_role == "garnish" and "тофу" in sub_alt:
                confidence += 0.10
            elif egg_role == "garnish" and "банан" in sub_alt:
                confidence -= 0.20

        # остальные
        if substitution.get("note") and len(substitution["note"]) > 20:
            confidence += 0.05
        if substitution.get("ratio") and substitution["ratio"] != 1.0:
            confidence += 0.03


        key = f"{ingredient.get('name', '')}->{substitution.get('alternative', '')}"
        self.substitution_confidence[key] = round(min(confidence, 1.0), 2)
        return self.substitution_confidence[key]

    # ── Применение замены ─────────────────────────────────────────────────

    def _apply_substitution(self, ingredients, original_ing, substitution, scale_factor):
        if original_ing.get("by_taste", False):
            scale_factor = 1.0
            quantity_value = 0
        else:
            quantity_value = original_ing.get("quantity", 0) or 0

        UNIT_MAP = {
            "молоко": "мл", "вода": "мл", "масло растительное": "мл",
            "соевое молоко": "мл", "миндальное молоко": "мл", "кокосовое молоко": "мл",
            "кефир": "мл", "сливки": "мл", "кокосовые сливки": "мл",
            "растительное молоко": "мл", "аквафаба": "мл",
            "мука": "г", "рисовая мука": "г", "миндальная мука": "г",
            "кокосовая мука": "г", "нутовая мука": "г", "гречневая мука": "г",
            "крахмал": "г", "сахар": "г", "соль": "г", "стевия": "г",
            "эритрит": "г", "какао": "г", "агар-агар": "г",
            "горох": "г", "фасоль": "г", "кукуруза": "г", "нут отварной": "г",
            "тофу": "г", "тофу (мягкий)": "г", "тофу (плотный)": "г",
            "творог": "г", "сыр": "г", "сметана": "г",
            "цветная капуста": "г", "брокколи": "г", "кабачок": "г",
            "грибы": "г", "авокадо": "г", "банан (пюре)": "г",
            "мясо": "г", "курица": "г", "сейтан": "г",
            "кокосовый амино соус": "мл", "тамари": "мл",
            "яйца": "шт", "банан": "шт","клубника": "г","малина": "г","ежевика": "г","ягоды": "г",

        }

        def _detect_unit(name):
            n = name.lower()
            if any(k in n for k in ["мука", "тофу", "капуста", "кабачок", "грибы", "мясо",
                                     "нут", "фасоль", "горох", "чечевица", "авокадо"]):
                return "г"
            if any(k in n for k in ["молоко", "сливки", "кефир", "вода", "масло", "соус", "аквафаба"]):
                return "мл"
            if any(k in n for k in ["яйц", "лимон", "банан"]):
                return "шт"
            return None

        alt_name = substitution.get("alternative", "")
        alt_lower = alt_name.lower()
        if "льняная" in alt_lower:
            new_unit = "ст.л"
        elif "сода + уксус" in alt_lower or "сода + лимон" in alt_lower:
            new_unit = "ч.л"
        elif alt_name in UNIT_MAP:
            new_unit = UNIT_MAP[alt_name]
        else:
            detected = _detect_unit(alt_name)
            new_unit = detected if detected else (
                "г" if original_ing.get("unit") == "банка" else original_ing.get("unit", "шт")
            )

        ratio = substitution.get("ratio", 1.0)
        if original_ing.get("unit") == "банка":
            original_quantity_grams = can_to_grams(original_ing.get("name", ""), quantity_value)
            new_quantity = original_quantity_grams * scale_factor * ratio
            new_unit = "г"
        else:
            new_quantity = quantity_value * scale_factor * ratio

        ing_name = original_ing.get("name", "")
        if "яйц" in ing_name and "льняная" in alt_name:
            new_quantity = quantity_value * 4
            new_unit = "ст.л"
        elif ing_name == "разрыхлитель" and "сода + уксус" in alt_name:
            new_quantity = quantity_value * 0.5
            new_unit = "ч.л"
        elif "масло сливочное" in ing_name and "растительное" in alt_name:
            new_quantity = quantity_value * 0.8
            new_unit = "мл"

        if original_ing.get("by_taste", False):
            substitute = {
                "name": alt_name, "quantity": None, "unit": "", "is_substitute": True,
                "original_name": ing_name, "by_taste": True,
            }
        else:
            substitute = {
                "name": alt_name, "quantity": round(new_quantity, 1), "unit": new_unit,
                "is_substitute": True, "original_name": ing_name,
            }

        for i, ing in enumerate(ingredients):
            if ing.get("name") == ing_name:
                ingredients[i] = substitute
                break

    # ── Расчёт количества порций ──────────────────────────────────────────

    def _calculate_servings(self, ingredients, manual_servings=None):
        if manual_servings and manual_servings > 0:
            return manual_servings
        total_weight = 0
        liquid_volume = 0
        for ing in ingredients:
            if ing.get("by_taste") or ing.get("quantity") is None:
                continue
            qty = ing["quantity"]
            unit = ing.get("unit", "")
            if unit == "банка":
                total_weight += can_to_grams(ing.get("name", ""), qty)
            elif unit == "г":
                total_weight += qty
            elif unit == "кг":
                total_weight += qty * 1000
            elif unit == "мл":
                liquid_volume += qty
            elif unit == "л":
                liquid_volume += qty * 1000
        if liquid_volume > total_weight * 0.5:
            servings = int((total_weight + liquid_volume) / 300)
        elif total_weight > 1000:
            servings = int(total_weight / 250)
        else:
            servings = int(total_weight / 150)
        return max(1, servings)

    # ── Основной метод адаптации ──────────────────────────────────────────

    def adapt_recipe(self, recipe: dict, user_products_text: str,
                     allergies=None, diet=None) -> dict:
        has_user_products = bool(user_products_text and user_products_text.strip())
        if has_user_products:
            user_products = self.parse_user_products(user_products_text)
            user_dict = {p["name"]: p for p in user_products}
        else:
            user_dict = {}

        recipe_ingredients = recipe["ingredients"].copy()
        processed_allergies = self._expand_allergies(allergies or [])
        dish_context = DishContextClassifier.classify(
            recipe.get("name", ""), recipe.get("category", "")
        )

        # Масштабирование
        scale_factor = 1.0
        if has_user_products:
            # Нормализуем user_dict для сравнения
            user_dict_normalized = {}
            for p in user_products:
                p_name = p["name"]
                # Сохраняем под нормализованным именем и под оригинальным
                user_dict_normalized[p_name] = p
                # Также пробуем найти в группах
                for group_name, members in self.INGREDIENT_GROUPS.items():
                    if p_name == group_name or p_name in members:
                        for member in members:
                            if member not in user_dict_normalized:
                                user_dict_normalized[member] = p

            min_scale = 1.0
            for ing in recipe_ingredients:
                if ing.get("by_taste") or ing.get("quantity") is None:
                    continue

                ing_name = ing["name"]
                ing_normalized = self.normalize_ingredient_name(ing_name)

                # Ищем продукт пользователя по разным вариантам имени
                user_product = None
                for key in [ing_name, ing_normalized]:
                    if key in user_dict_normalized:
                        user_product = user_dict_normalized[key]
                        break

                # Также проверяем группы
                if not user_product:
                    for group_name, members in self.INGREDIENT_GROUPS.items():
                        if ing_normalized == group_name or ing_normalized in members:
                            if group_name in user_dict_normalized:
                                user_product = user_dict_normalized[group_name]
                                break
                            for member in members:
                                if member in user_dict_normalized:
                                    user_product = user_dict_normalized[member]
                                    break
                        if user_product:
                            break

                if user_product:
                    uq = user_product["quantity"]
                    if uq is not None and uq > 0 and uq < ing["quantity"]:
                        min_scale = min(min_scale, uq / ing["quantity"])

            scale_factor = min_scale

            # Также проверяем максимальное масштабирование (если продуктов больше)
            max_scale = scale_factor
            for ing in recipe_ingredients:
                if ing.get("by_taste") or ing.get("quantity") is None:
                    continue

                ing_name = ing["name"]
                ing_normalized = self.normalize_ingredient_name(ing_name)

                user_product = None
                for key in [ing_name, ing_normalized]:
                    if key in user_dict_normalized:
                        user_product = user_dict_normalized[key]
                        break

                if not user_product:
                    for group_name, members in self.INGREDIENT_GROUPS.items():
                        if ing_normalized == group_name or ing_normalized in members:
                            if group_name in user_dict_normalized:
                                user_product = user_dict_normalized[group_name]
                                break
                            for member in members:
                                if member in user_dict_normalized:
                                    user_product = user_dict_normalized[member]
                                    break
                        if user_product:
                            break

                if user_product:
                    uq = user_product["quantity"]
                    if uq is not None and uq > 0 and uq > ing["quantity"] * scale_factor:
                        max_scale = max(max_scale, uq / ing["quantity"])

            scale_factor = max_scale

        # Разметка ингредиентов
        scaled_ingredients = []
        missing, short, available, explicitly_missing, excess_info = [], [], [], [], []

        for ing in recipe_ingredients:
            if ing.get("by_taste", False):
                scaled_ingredients.append({**ing, "quantity": None, "unit": "", "by_taste": True})
                continue
            if ing.get("quantity") is None:
                scaled_ingredients.append(ing)
                continue

            new_quantity = ing["quantity"] * scale_factor
            ing_name = ing["name"]
            ing_normalized = self.normalize_ingredient_name(ing_name)

            # Ищем продукт пользователя
            user_product = None
            if has_user_products:
                for key in [ing_name, ing_normalized]:
                    if key in user_dict:
                        user_product = user_dict[key]
                        break

                # Проверяем группы
                if not user_product:
                    for group_name, members in self.INGREDIENT_GROUPS.items():
                        if ing_normalized == group_name or ing_normalized in members:
                            if group_name in user_dict:
                                user_product = user_dict[group_name]
                                break
                            for member in members:
                                if member in user_dict:
                                    user_product = user_dict[member]
                                    break
                        if user_product:
                            break

            if user_product:
                uq = user_product["quantity"]
                if uq is None:
                    scaled_ingredients.append({**ing, "quantity": round(new_quantity, 1)})
                elif uq == 0:
                    scaled_ingredients.append({**ing, "quantity": round(new_quantity, 1), "missing": True})
                    explicitly_missing.append(ing)
                    missing.append(ing)
                elif uq >= new_quantity:
                    if uq > new_quantity * 1.05:
                        excess_info.append({
                            "name": ing["name"],
                            "recipe_needs": round(new_quantity, 1),
                            "user_has": uq,
                            "excess": round(uq - new_quantity, 1),
                            "unit": ing["unit"],
                        })
                    scaled_ingredients.append({**ing, "quantity": round(new_quantity, 1)})
                    available.append(ing)
                else:
                    # У пользователя МЕНЬШЕ, чем нужно - уменьшаем рецепт
                    actual_quantity = uq * (new_quantity / ing["quantity"])  # пропорционально
                    scaled_ingredients.append({
                        **ing, "quantity": round(uq, 1), "limited": True,
                        "original_quantity": round(new_quantity, 1),
                    })
                    short.append({**ing, "user_quantity": uq, "shortage": round(new_quantity - uq, 1)})
            else:
                if has_user_products:
                    scaled_ingredients.append({**ing, "quantity": round(new_quantity, 1), "missing": True})
                    missing.append(ing)
                else:
                    scaled_ingredients.append({**ing, "quantity": round(ing["quantity"], 1)})
                    available.append(ing)

        # Анализ диеты
        diet_issues = []
        if diet and diet != "Нет":
            for ing in recipe_ingredients:
                # Используем нормализованное имя для проверки
                ing_normalized = self.normalize_ingredient_name(ing["name"])
                ing_for_check = ing.copy()
                ing_for_check["name"] = ing_normalized

                compatible, _, _ = diet_analyzer.check_compatibility(
                    ing_for_check, diet, dish_context=dish_context
                )
                if not compatible and not any(d["name"] == ing["name"] for d in diet_issues):
                    diet_issues.append({**ing, "diet": diet})

        # Анализ аллергий
        problem_allergies = []
        if processed_allergies:
            for ing in recipe_ingredients:
                ing_info = self.manager.get_ingredient_info(ing["name"])
                if ing_info and ing_info.get("allergens"):
                    for allergen in processed_allergies:
                        if allergen.lower() in [a.lower() for a in ing_info["allergens"]]:
                            if not any(pa["name"] == ing["name"] for pa in problem_allergies):
                                problem_allergies.append({**ing, "allergen": allergen, "info": ing_info})

        # Подбор замен
        issues_to_resolve = {}
        for ing in diet_issues:
            issues_to_resolve.setdefault(ing["name"], {"ingredient": ing, "reasons": []})
            issues_to_resolve[ing["name"]]["reasons"].append(f"diet_{diet}")
        for ing in problem_allergies:
            issues_to_resolve.setdefault(ing["name"], {"ingredient": ing, "reasons": []})
            issues_to_resolve[ing["name"]]["reasons"].append(f"allergy_{ing['allergen']}")
        for ing in explicitly_missing:
            issues_to_resolve.setdefault(ing["name"], {"ingredient": ing, "reasons": []})
            issues_to_resolve[ing["name"]]["reasons"].append("explicitly_missing")

        substitutions_made = []
        alternatives_for_display = []

        for key, issue_data in issues_to_resolve.items():
            ing = issue_data["ingredient"]
            reasons = issue_data["reasons"]
            search_reason = None
            if any("allergy_" in r for r in reasons):
                search_reason = next(
                    (r.replace("allergy_", "") for r in reasons if r.startswith("allergy_")), None
                )
            elif any("diet_" in r for r in reasons):
                search_reason = diet

            context_alts = diet_analyzer.find_alternatives(ing["name"], search_reason, dish_context=dish_context)


            db_subs = self.manager.find_substitutions(ing["name"], search_reason)
            ingredient_alternatives = []
            best_sub = None
            best_confidence = 0.0

            for alt in context_alts:
                fake_sub = {
                    "ingredient": ing["name"], "alternative": alt["name"],
                    "ratio": alt.get("ratio", 1.0), "note": alt.get("description", ""),
                    "condition": search_reason or "всегда",
                }
                conf = self._check_substitution_confidence(fake_sub, ing, dish_context)
                ingredient_alternatives.append({
                    "name": alt["name"], "ratio": alt.get("ratio", 1.0),
                    "note": alt.get("description", ""), "confidence": conf,
                    "condition": search_reason or "всегда",
                })
                if conf > best_confidence:
                    best_confidence = conf
                    best_sub = fake_sub

            for sub in db_subs:
                conf = self._check_substitution_confidence(sub, ing, dish_context)
                alt_name = sub["alternative"]
                if not any(a["name"] == alt_name for a in ingredient_alternatives):
                    ingredient_alternatives.append({
                        "name": alt_name, "ratio": sub.get("ratio", 1.0),
                        "note": sub.get("note", ""), "confidence": conf,
                        "condition": sub.get("condition", "всегда"),
                    })
                    if conf > best_confidence:
                        best_confidence = conf
                        best_sub = sub

            if ingredient_alternatives:
                alternatives_for_display.append({
                    "original": ing["name"],
                    "alternatives": sorted(ingredient_alternatives, key=lambda x: x["confidence"], reverse=True),
                })

            if best_sub and best_confidence > 0.5:
                reason_text = []
                for r in reasons:
                    if r.startswith("allergy_"):
                        reason_text.append(f"аллергия на {r.replace('allergy_', '')}")
                    elif r.startswith("diet_"):
                        reason_text.append(f"диета {diet}")
                    elif r == "explicitly_missing":
                        reason_text.append("указано с 0")
                substitutions_made.append({
                    "original": ing["name"],
                    "alternative": best_sub.get("alternative", best_sub.get("name", "")),
                    "reason": ", ".join(reason_text),
                    "note": best_sub.get("note", best_sub.get("description", "")),
                    "confidence": best_confidence,
                    "ratio": best_sub.get("ratio", 1.0),
                })
                self._apply_substitution(scaled_ingredients, ing, best_sub, scale_factor)

        manual_servings = recipe.get("servings")
        servings = self._calculate_servings(scaled_ingredients, manual_servings)

        issues_for_check = []
        for ing in diet_issues + problem_allergies:
            best = next((s for s in substitutions_made if s["original"] == ing["name"]), None)
            issues_for_check.append({"name": ing["name"], "best_sub_name": best["alternative"] if best else ""})
        feasibility = AdaptationFeasibilityChecker.check(recipe, issues_for_check, dish_context)

        return {
            "recipe_name": recipe["name"],
            "ingredients": scaled_ingredients,
            "missing": missing,
            "explicitly_missing": explicitly_missing,
            "short": short,
            "available": available,
            "excess": excess_info,
            "diet_issues": diet_issues,
            "allergy_issues": problem_allergies,
            "substitutions": substitutions_made,
            "alternatives": alternatives_for_display,
            "scale_factor": scale_factor,
            "steps": recipe.get("steps", []),
            "servings": servings,
            "dish_context": dish_context,
            "feasibility": feasibility,
        }
