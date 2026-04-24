import streamlit as st
import json
import re
import pandas as pd
from typing import List, Dict, Optional
import os

from diet_analyzer import diet_analyzer, analyze_diet_compatibility


# Подключение внешних стилей
def load_css():
    # Загружает CSS из внешнего файла
    css_file = "static/css/style.css"
    if os.path.exists(css_file):
        with open(css_file, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


class RecipeManager:
    # Управление базой рецептов
    def __init__(self, recipes_file="data/recipes.json",
                 ingredients_file="data/ingredients.json",
                 substitutions_file="data/substitutions.json"):
        self.recipes_file = recipes_file
        self.ingredients_file = ingredients_file
        self.substitutions_file = substitutions_file

        self.recipes = self._load_json(recipes_file).get("recipes", [])
        self.ingredients = self._load_json(ingredients_file).get("ingredients", [])
        self.substitutions = self._load_json(substitutions_file).get("substitutions", [])

    def _load_json(self, filename):
        # Загружает JSON файл
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}

    def _save_json(self, data, filename):
        # Сохраняет JSON файл
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all_recipes(self):
        # Возвращает все рецепты
        return self.recipes

    def get_recipe_by_id(self, recipe_id):
        # Находит рецепт по ID
        for recipe in self.recipes:
            if recipe.get("id") == recipe_id:
                return recipe
        return None

    def get_recipes_by_category(self, category):
        # Возвращает рецепты по категории
        return [r for r in self.recipes if r.get("category") == category]

    def search_recipes(self, query):
        # Ищет рецепты по названию
        query = query.lower()
        return [r for r in self.recipes if query in r["name"].lower()]

    def add_recipe(self, recipe):
        # Добавляет новый рецепт
        new_id = max([r.get("id", 0) for r in self.recipes] + [0]) + 1
        recipe["id"] = new_id
        self.recipes.append(recipe)
        self._save_json({"recipes": self.recipes}, self.recipes_file)
        return new_id

    def get_ingredient_info(self, name):
        # Информация об ингредиенте
        for ing in self.ingredients:
            if ing["name"] == name:
                return ing
        return None

    def find_substitutions(self, ingredient, reason=None):
        # Ищет замены для ингредиента
        result = []
        for sub in self.substitutions:
            # Проверяем вхождение (чтобы "горох" подходило для "горох консервированный")
            if sub["ingredient"] in ingredient or ingredient in sub["ingredient"]:
                # Если reason не указан - возвращаем все замены
                if reason is None:
                    result.append(sub)
                elif reason and sub.get("condition") == reason:
                    result.append(sub)
                elif reason and sub.get("condition").lower() == reason.lower():
                    result.append(sub)
                elif not reason and sub.get("condition") in ["всегда", "любая"]:
                    result.append(sub)
        return result


class RecipeAdapter:
    # Адаптация рецептов под продукты пользователя

    def __init__(self):
        self.manager = RecipeManager()
        self.substitution_confidence = {}

    def parse_user_products(self, text):
        # Парсит продукты пользователя с поддержкой нулевых значений
        products = []
        for item in text.split(','):
            item = item.strip()
            if not item:
                continue

            # Определяем, является ли продукт консервированным
            is_canned = 'консервированный' in item or 'консервированная' in item or 'консервированное' in item or 'баночный' in item or 'баночная' in item or 'банка' in item

            # Поддерживаем форматы:
            match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|шт|г|мл|ст\.л|ч\.л|кг|л)?', item)
            if match:
                name = match.group(1).strip().lower()
                name = self.normalize_ingredient_name(name)
                quantity = float(match.group(2).replace(',', '.'))
                unit = match.group(3) if match.group(3) else 'шт'

                # Если продукт консервированный и единица измерения "шт", меняем на "банка"
                if is_canned and unit == 'шт':
                    unit = 'банка'

                # Нормализуем единицы измерения для банок
                if unit in ['банка', 'банки', 'банок', 'б']:
                    unit = 'банка'

                products.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit
                })
            else:
                name = self.normalize_ingredient_name(item.lower())
                # Если продукт консервированный, используем банку как единицу
                unit = 'банка' if is_canned else 'шт'
                products.append({
                    'name': name,
                    'quantity': None,
                    'unit': unit
                })
        return products

    def check_allergies(self, ingredients, allergies):
        # Проверяет ингредиенты на аллергены
        problem_ingredients = []
        for ing in ingredients:
            ing_info = self.manager.get_ingredient_info(ing['name'])
            if ing_info and ing_info.get('allergens'):
                for allergen in allergies:
                    if allergen.lower() in [a.lower() for a in ing_info['allergens']]:
                        problem_ingredients.append({
                            **ing,
                            'allergen': allergen,
                            'info': ing_info
                        })
        return problem_ingredients

    def _analyze_diet_compatibility(self, ingredient, diet):
        # ИИ: анализ совместимости ингредиента с диетой
        compatible, alternatives = analyze_diet_compatibility(ingredient, diet)

        if not compatible:
            return False, alternatives

        return True, None

    def analyze_full_recipe_diet(self, ingredients, diet):
        return diet_analyzer.analyze_recipe_for_diet(ingredients, diet)

    def _calculate_optimal_scale(self, ingredients, user_dict, scale_factor_from_short):
        """
        ИИ: расчет оптимального коэффициента масштабирования
        Учитывает как недостаток, так и избыток продуктов
        """
        # Начинаем с коэффициента от недостатка
        optimal_scale = scale_factor_from_short

        # Проверяем избыток продуктов
        for ing in ingredients:
            if ing['name'] in user_dict:
                user_q = user_dict[ing['name']]['quantity']
                if user_q > 0 and user_q > ing['quantity']:
                    # Если у пользователя больше, чем нужно
                    potential_scale = user_q / ing['quantity']
                    # Берем максимальный коэффициент (чтобы использовать весь избыток)
                    if potential_scale > optimal_scale:
                        optimal_scale = potential_scale

        return optimal_scale

    def _optimize_portions(self, ingredients, user_dict, scale_factor):
        """
        ИИ: оптимизация рецепта с единым коэффициентом масштабирования
        """
        optimized_ingredients = []
        excess_info = []

        for ing in ingredients:
            new_quantity = ing['quantity'] * scale_factor

            # Проверяем, есть ли у пользователя этот продукт в достаточном количестве
            if ing['name'] in user_dict:
                user_q = user_dict[ing['name']]['quantity']
                if user_q > 0 and user_q >= new_quantity:
                    # У пользователя есть достаточно, используем рассчитанное количество
                    if user_q > new_quantity * 1.1:  # Если есть значительный избыток (>10%)
                        excess_info.append({
                            'name': ing['name'],
                            'current': ing['quantity'],
                            'scaled': new_quantity,
                            'available': user_q,
                            'excess': user_q - new_quantity,
                            'unit': ing['unit']
                        })
                    optimized_ingredients.append({
                        **ing,
                        'quantity': round(new_quantity, 1)
                    })
                elif user_q > 0 and user_q < new_quantity:
                    # У пользователя есть, но меньше чем нужно по новому масштабу
                    # Используем то, что есть
                    optimized_ingredients.append({
                        **ing,
                        'quantity': user_q,
                        'limited': True,
                        'original_quantity': new_quantity
                    })
                else:
                    # Продукта нет (user_q == 0)
                    optimized_ingredients.append({
                        **ing,
                        'quantity': new_quantity,
                        'missing': True
                    })
            else:
                # Продукта нет в списке пользователя
                optimized_ingredients.append({
                    **ing,
                    'quantity': new_quantity,
                    'missing': True
                })

        return optimized_ingredients, excess_info

    def adapt_recipe(self, recipe, user_products_text, allergies=None, diet=None):
        # Адаптирует рецепт под наличие продуктов

        # Проверяем, ввел ли пользователь продукты
        has_user_products = user_products_text and user_products_text.strip() != ""

        # Если пользователь не указал продукты, создаем пустой словарь
        if not has_user_products:
            user_dict = {}
        else:
            user_products = self.parse_user_products(user_products_text)
            user_dict = {p['name']: p for p in user_products}

        recipe_ingredients = recipe['ingredients'].copy()

        # Обработка аллергий: если указано "молоко", добавляем "лактозу"
        processed_allergies = []
        if allergies:
            for allergy in allergies:
                allergy_lower = allergy.lower().strip()
                processed_allergies.append(allergy_lower)
                if allergy_lower == 'молоко':
                    processed_allergies.append('лактоза')
                if allergy_lower in ['молочка', 'молочные', 'молочные продукты']:
                    processed_allergies.append('лактоза')

        processed_allergies = list(set(processed_allergies))

        missing = []
        short = []
        diet_issues = []
        available = []
        explicitly_missing = []

        CORE_INGREDIENTS = ['мука', 'яйца', 'молоко', 'творог', 'мясо', 'рыба', 'крупа', 'рис', 'колбаса', 'курица']
        MINOR_INGREDIENTS = ['разрыхлитель', 'сода', 'соль', 'перец', 'специи', 'ванилин']

        base_scale = 1.0

        for ing in recipe_ingredients:
            # Проверка совместимости с диетой
            if diet and diet != "Нет":
                compatible, alternative = self._analyze_diet_compatibility(ing, diet)
                if not compatible:
                    diet_issues.append({
                        **ing,
                        'diet': diet,
                        'alternative': alternative
                    })

            if ing['name'] in user_dict:
                user_q = user_dict[ing['name']]['quantity']

                if user_q is None:
                    available.append(ing)
                elif user_q == 0:
                    explicitly_missing.append(ing)
                    missing.append(ing)
                elif user_q < ing['quantity']:
                    short.append({
                        **ing,
                        'user_quantity': user_q,
                        'shortage': ing['quantity'] - user_q
                    })
                    scale_from_this = user_q / ing['quantity']
                    if scale_from_this < base_scale:
                        base_scale = scale_from_this
                else:
                    available.append(ing)
            else:
                # Если пользователь не вводил продукты, считаем что продукт есть
                if not has_user_products:
                    available.append(ing)
                else:
                    missing.append(ing)

        # Проверка аллергий
        problem_allergies = []
        if processed_allergies:
            for ing in recipe_ingredients:
                ing_info = self.manager.get_ingredient_info(ing['name'])
                if ing_info and ing_info.get('allergens'):
                    for allergen in processed_allergies:
                        if allergen.lower() in [a.lower() for a in ing_info['allergens']]:
                            already_added = False
                            for pa in problem_allergies:
                                if pa['name'] == ing['name']:
                                    already_added = True
                                    break
                            if not already_added:
                                problem_allergies.append({
                                    **ing,
                                    'allergen': allergen,
                                    'info': ing_info
                                })

        # Расчет оптимального масштаба - ТОЛЬКО если пользователь вводил продукты
        optimal_scale = 1.0
        if has_user_products:
            optimal_scale = base_scale

            for ing in recipe_ingredients:
                if ing['name'] in user_dict:
                    user_q = user_dict[ing['name']]['quantity']
                    if user_q is not None and user_q > 0 and user_q > ing['quantity'] * optimal_scale:
                        potential_scale = user_q / ing['quantity']
                        if potential_scale > optimal_scale:
                            optimal_scale = potential_scale

        # Применяем масштабирование
        scaled_ingredients = []
        excess_info = []

        for ing in recipe_ingredients:
            new_quantity = ing['quantity'] * optimal_scale

            if ing['name'] in user_dict:
                user_q = user_dict[ing['name']]['quantity']

                if user_q is None:
                    scaled_ingredients.append({
                        **ing,
                        'quantity': round(new_quantity, 1)
                    })
                elif user_q > 0 and user_q >= new_quantity:
                    if user_q > new_quantity * 1.05:
                        excess_info.append({
                            'name': ing['name'],
                            'recipe_needs': round(new_quantity, 1),
                            'user_has': user_q,
                            'excess': round(user_q - new_quantity, 1),
                            'unit': ing['unit']
                        })
                    scaled_ingredients.append({
                        **ing,
                        'quantity': round(new_quantity, 1)
                    })
                elif user_q > 0 and user_q < new_quantity:
                    scaled_ingredients.append({
                        **ing,
                        'quantity': user_q,
                        'limited': True,
                        'original_quantity': round(new_quantity, 1)
                    })
                else:
                    scaled_ingredients.append({
                        **ing,
                        'quantity': round(new_quantity, 1),
                        'missing': True
                    })
            else:
                # Если пользователь не вводил продукты, используем оригинальное количество
                scaled_ingredients.append({
                    **ing,
                    'quantity': round(ing['quantity'], 1)
                })

        # Собираем проблемы для замены
        issues_to_resolve = {}

        # Добавляем аллергии
        for ing in problem_allergies:
            ing_name = ing['name']
            if ing_name not in issues_to_resolve:
                issues_to_resolve[ing_name] = {
                    'ingredient': ing,
                    'reasons': []
                }
            issues_to_resolve[ing_name]['reasons'].append(f"allergy_{ing['allergen']}")

        # Добавляем проблемы с диетой - ВАЖНО: добавляем ВСЕ diet_issues
        for ing in diet_issues:
            ing_name = ing['name']
            if ing_name not in issues_to_resolve:
                issues_to_resolve[ing_name] = {
                    'ingredient': ing,
                    'reasons': []
                }
            # Проверяем, нет ли уже аллергии на этот продукт
            has_allergy = any(f"allergy_" in r for r in issues_to_resolve[ing_name]['reasons'])
            if not has_allergy:
                issues_to_resolve[ing_name]['reasons'].append(f"diet_{diet}")

        # Добавляем явно отсутствующие (указанные с 0)
        for ing in explicitly_missing:
            ing_name = ing['name']
            if ing_name not in issues_to_resolve:
                issues_to_resolve[ing_name] = {
                    'ingredient': ing,
                    'reasons': []
                }
                issues_to_resolve[ing_name]['reasons'].append('explicitly_missing')

        # Добавляем также продукты, которые есть в наличии, но не подходят по диете
        # (если пользователь не вводил продукты, но указал диету)
        for ing in recipe_ingredients:
            ing_name = ing['name']
            # Проверяем, не входит ли этот ингредиент в diet_issues
            is_in_diet_issues = False
            for di in diet_issues:
                if di['name'] == ing_name:
                    is_in_diet_issues = True
                    break

            if is_in_diet_issues and ing_name not in issues_to_resolve:
                issues_to_resolve[ing_name] = {
                    'ingredient': ing,
                    'reasons': []
                }
                issues_to_resolve[ing_name]['reasons'].append(f"diet_{diet}")

        print(f"DEBUG: issues_to_resolve = {list(issues_to_resolve.keys())}")  # Временный отладчик

        substitutions_made = []
        alternatives_for_display = []

        # Ищем замены для проблемных ингредиентов
        for key, issue_data in issues_to_resolve.items():
            ing = issue_data['ingredient']
            reasons = issue_data['reasons']

            # Определяем причину для поиска замены
            search_reason = None
            if any('allergy_' in r for r in reasons):
                for r in reasons:
                    if r.startswith('allergy_'):
                        search_reason = r.replace('allergy_', '')
                        break
            elif any('diet_' in r for r in reasons):
                search_reason = diet  # Используем оригинальное название диеты
            elif 'explicitly_missing' in reasons:
                search_reason = None

            print(f"Поиск замены для: {ing['name']}, причина: {search_reason}")  # Отладка

            # Ищем замены
            subs = self.manager.find_substitutions(ing['name'], search_reason)

            print(f"Найдено замен: {len(subs)}")  # Отладка

            # Собираем все подходящие альтернативы
            ingredient_alternatives = []
            best_sub = None
            best_confidence = 0

            for sub in subs:
                confidence = self._check_substitution_confidence(sub, ing)
                ingredient_alternatives.append({
                    'name': sub['alternative'],
                    'ratio': sub.get('ratio', 1.0),
                    'note': sub.get('note', ''),
                    'confidence': confidence,
                    'condition': sub.get('condition', 'всегда')
                })

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_sub = sub

            if ingredient_alternatives:
                alternatives_for_display.append({
                    'original': ing['name'],
                    'alternatives': sorted(ingredient_alternatives, key=lambda x: x['confidence'], reverse=True)
                })

            if best_sub and best_confidence > 0.5:
                reason_text = []
                if any('allergy_' in r for r in reasons):
                    for r in reasons:
                        if r.startswith('allergy_'):
                            reason_text.append(f"аллергия на {r.replace('allergy_', '')}")
                if any('diet_' in r for r in reasons):
                    reason_text.append(f"диета {diet}")
                if 'explicitly_missing' in reasons:
                    reason_text.append("указано с 0")

                substitutions_made.append({
                    'original': ing['name'],
                    'alternative': best_sub['alternative'],
                    'reason': ", ".join(reason_text),
                    'note': best_sub.get('note', ''),
                    'confidence': best_confidence,
                    'ratio': best_sub.get('ratio', 1.0)
                })

                # Применяем замену
                self._apply_substitution(scaled_ingredients, ing, best_sub, 1.0)

        # Расчет порций
        manual_servings = recipe.get('servings', None)
        servings = self._calculate_servings(scaled_ingredients, manual_servings)

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
            'scale_factor': optimal_scale,
            'steps': recipe.get('steps', []),
            'servings': servings
        }

    

    def _check_substitution_confidence(self, substitution, ingredient):
        # ИИ: оценка уверенности в замене
        confidence = 0.8

        if 'note' in substitution:
            if 'выпечка' in substitution['note'] and ingredient.get('name') in ['мука', 'яйца']:
                confidence += 0.1

        key = f"{ingredient['name']}->{substitution['alternative']}"
        self.substitution_confidence[key] = confidence

        return confidence

    def _apply_substitution(self, ingredients, original_ing, substitution, scale_factor):
        # Применяет замену для проблемного ингредиента

        unit_mapping = {
            'молоко': 'мл',
            'вода': 'мл',
            'масло растительное': 'мл',
            'соевое молоко': 'мл',
            'миндальное молоко': 'мл',
            'кокосовое молоко': 'мл',
            'мука': 'г',
            'рисовая мука': 'г',
            'миндальная мука': 'г',
            'сахар': 'г',
            'соль': 'г',
            'стевия': 'г',
            'яйца': 'шт',
            'лимон': 'шт',
            'горох': 'г',
            'фасоль': 'г',
            'кукуруза': 'г',
            'банка': 'г'  # банка конвертируется в граммы
        }

        if 'льняная мука' in substitution['alternative']:
            new_unit = 'ст.л'
        elif 'сода + уксус' in substitution['alternative']:
            new_unit = 'ч.л'
        elif substitution['alternative'] in unit_mapping:
            new_unit = unit_mapping[substitution['alternative']]
        else:
            new_unit = original_ing['unit']

        ratio = substitution.get('ratio', 1.0)

        # Если оригинальный ингредиент был в банках, конвертируем в граммы
        if original_ing.get('unit') == 'банка':
            can_to_grams = {
                "горох": 400,
                "фасоль": 400,
                "кукуруза": 340,
                "нут": 400,
                "чечевица": 400
            }
            grams_per_can = can_to_grams.get(original_ing['name'], 400)
            original_quantity_grams = original_ing['quantity'] * grams_per_can
            new_quantity = original_quantity_grams * scale_factor * ratio
            new_unit = 'г'
        else:
            new_quantity = original_ing['quantity'] * scale_factor * ratio

        # Специальная обработка
        if original_ing['name'] == 'яйца' and 'льняная мука' in substitution['alternative']:
            new_quantity = original_ing['quantity'] * 4
            new_unit = 'ст.л'
        elif original_ing['name'] == 'разрыхлитель' and 'сода + уксус' in substitution['alternative']:
            new_quantity = original_ing['quantity'] * 0.5
            new_unit = 'ч.л'
        elif 'масло сливочное' in original_ing['name'] and 'растительное масло' in substitution['alternative']:
            new_quantity = original_ing['quantity'] * 0.8
            new_unit = 'мл'

        substitute_ingredient = {
            'name': substitution['alternative'],
            'quantity': round(new_quantity, 1),
            'unit': new_unit,
            'is_substitute': True,
            'original_name': original_ing['name']
        }

        # Заменяем ингредиент
        for i, ing in enumerate(ingredients):
            if ing['name'] == original_ing['name']:
                ingredients[i] = substitute_ingredient
                break

    def _calculate_servings(self, ingredients, manual_servings=None):
        # ИИ: расчет количества порций на основе ингредиентов

        if manual_servings and manual_servings > 0:
            return manual_servings

        total_weight = 0
        liquid_volume = 0

        # Конвертация банок в граммы
        can_to_grams = {
            "горох": 400,
            "фасоль": 400,
            "кукуруза": 340,
            "нут": 400,
            "чечевица": 400
        }

        for ing in ingredients:
            if ing.get('unit') == 'банка':
                # Конвертируем банки в граммы
                product_name = ing['name']
                grams_per_can = can_to_grams.get(product_name, 400)
                total_weight += ing['quantity'] * grams_per_can
            elif ing.get('unit') in ['г', 'кг']:
                if ing['unit'] == 'кг':
                    total_weight += ing['quantity'] * 1000
                else:
                    total_weight += ing['quantity']
            elif ing.get('unit') in ['мл', 'л']:
                if ing['unit'] == 'л':
                    liquid_volume += ing['quantity'] * 1000
                else:
                    liquid_volume += ing['quantity']

        if liquid_volume > total_weight * 0.5:
            servings = int((total_weight + liquid_volume) / 300)
        elif total_weight > 1000:
            servings = int(total_weight / 250)
        else:
            servings = int(total_weight / 150)

        return max(1, servings)

    def _parse_recipe_text(self, text):
        # Парсит ингредиенты из текста
        ingredients = []
        lines = text.split('\n')
        for line in lines:
            # Поддерживаем банки в рецептах
            match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)', line)
            if match:
                name = match.group(1).strip().lower()
                name = self.normalize_ingredient_name(name)
                quantity = float(match.group(2).replace(',', '.'))
                unit = match.group(3)

                if unit in ['банка', 'банки', 'банок', 'б']:
                    unit = 'банка'
                    # Конвертируем банки в граммы для расчетов (1 банка = 400г)
                    # Но сохраняем оригинальную единицу для отображения

                ingredients.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit
                })
        return ingredients

    def normalize_ingredient_name(self, name):
        """Нормализует название ингредиента (обрабатывает синонимы)"""
        name_lower = name.lower().strip()

        # Словарь синонимов
        synonyms = {
            # Бобовые
            "горошек": "горох",
            "консервированный горох": "горох",
            "консервированный горошек": "горох",
            "баночный горох": "горох",
            "баночный горошек": "горох",
            "горох консервированный": "горох",
            "горошек консервированный": "горох",
            "горох в банке": "горох",
            "горошек в банке": "горох",
            "консервированная фасоль": "фасоль",
            "баночная фасоль": "фасоль",
            "фасоль в банке": "фасоль",
            "фасоль консервированная": "фасоль",
            "консервированный нут": "нут",
            "баночный нут": "нут",
            "нут консервированный": "нут",

            # Кукуруза
            "консервированная кукуруза": "кукуруза",
            "баночная кукуруза": "кукуруза",
            "кукуруза в банке": "кукуруза",
            "сладкая кукуруза": "кукуруза",
            "кукуруза консервированная": "кукуруза",

            # Молочные продукты
            "коровье молоко": "молоко",
            "домашнее молоко": "молоко",
            "сливочное маслице": "масло сливочное",

            # Мясо
            "куриное филе": "курица",
            "куриная грудка": "курица",
            "филе куриное": "курица",
            "грудка куриная": "курица",
            "свинина": "мясо",
            "говядина": "мясо",

            # Овощи
            "картошка": "картофель",
            "картофелька": "картофель",
        }

        # Проверяем точное совпадение
        if name_lower in synonyms:
            return synonyms[name_lower]

        # Проверяем вхождение (для фраз типа "горошек зеленый консервированный")
        for key, value in synonyms.items():
            if key in name_lower:
                return value

        return name_lower


# Инициализация
adapter = RecipeAdapter()

# Настройка страницы
st.set_page_config(
    page_title="Умный адаптер рецептов",
    page_icon="🍳",
    layout="wide"
)

# Загрузка стилей
load_css()

st.markdown('<h1 class="main-header">Умный адаптер рецептов</h1>', unsafe_allow_html=True)

with st.sidebar:
    with st.expander("Как это работает", expanded=False):
        st.markdown("""
        1. **Выбери рецепт** из базы
        2. **Укажи продукты**, которые есть (формат: название количество единица)
        3. **Добавь аллергии** и выбери диету
        4. **Получи адаптированный рецепт** с заменами!

        **Совет:** Если оставить поле продуктов пустым - система будет считать, что у вас есть всё
        """)

    with st.expander("Где используется ИИ", expanded=False):
        st.write("• Оценка уверенности в заменах продуктов")
        st.write("• Расчет оптимальных пропорций при избытке")
        st.write("• Анализ совместимости с диетой")
        st.write("• Определение количества порций")
        st.write("• Классификация типов блюд")

# Инициализация session_state для управления вкладками
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0  # 0 - база рецептов, 1 - добавление


# Функция для переключения вкладки
def switch_to_recipes_tab():
    st.session_state.active_tab = 0


tab1, tab2 = st.tabs(["Выбрать из базы", "Добавить рецепт"])

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

            st.markdown("### Ингредиенты:")
            for ing in selected_recipe['ingredients']:
                st.markdown(f"• {ing['name']}: {ing['quantity']}{ing['unit']}")
        else:
            st.warning("Рецепты не найдены")

    if filtered_recipes and 'selected_recipe' in locals():
        st.markdown("---")

        st.subheader("Какие продукты у тебя есть?")
        st.caption("Формат: продукт количество единица (например: мука 500г, яйца 3 шт)")

        # Компактное поле ввода с подсказкой в help
        user_products = st.text_area(
            "Введи продукты через запятую",
            placeholder="мука 500г, яйца 3 шт, молоко 200мл, горох 1 банка, разрыхлитель 0г",
            key="products_tab1",
            height=80,
            help="""
        Если оставить пустым - будем считать, что у вас есть все продукты\n
        Если продукта нет - указать 0 (например: разрыхлитель 0г, молоко 0мл)"""
        )

        col1, col2 = st.columns(2)
        with col1:
            allergies_input = st.text_input(
                "Аллергии (через запятую)",
                placeholder="лактоза, глютен, яйца",
                help="Если указать 'молоко', автоматически добавится аллергия на лактозу"
            )
        with col2:
            diet = st.selectbox(
                "Диета",
                ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"],
                key="diet_tab1"
            )

        if st.button("Адаптировать рецепт", type="primary", use_container_width=True):
            # Проверяем: если поле продуктов пустое, но есть аллергии или диета не "Нет" - всё равно работаем
            if user_products or (allergies_input) or (diet != "Нет"):
                allergies = [a.strip().lower() for a in allergies_input.split(',')] if allergies_input else []

                with st.spinner("ИИ анализирует рецепт..."):
                    result = adapter.adapt_recipe(
                        selected_recipe,
                        user_products if user_products else "",  # передаем пустую строку, если нет продуктов
                        allergies,
                        diet
                    )

                st.markdown("---")
                st.markdown(f"## {result['recipe_name']}")

                # Показываем порции
                st.markdown(f"### Примерно на {result['servings']} персон")

                # Информация о масштабировании
                if result['scale_factor'] != 1.0:
                    if result['scale_factor'] < 1.0:
                        st.info(f"**Рецепт уменьшен на {int((1 - result['scale_factor']) * 100)}%**")
                    else:
                        st.info(f"**Рецепт увеличен в {result['scale_factor']:.1f} раз**")

                # Показываем избыток продуктов
                if result['excess']:
                    with st.expander("Обнаружен избыток продуктов - рецепт увеличен"):
                        for e in result['excess']:
                            st.write(f"• {e['name']}: нужно {e['recipe_needs']}{e['unit']}, "
                                     f"у вас {e['user_has']}{e['unit']} (останется {e['excess']}{e['unit']})")

                if result['short']:
                    with st.expander("Продуктов меньше нормы"):
                        for s in result['short']:
                            st.write(
                                f"• {s['name']}: нужно {s['quantity']}{s['unit']}, есть {s['user_quantity']}{s['unit']}")
                        st.info("💡 Если продукта нет - указать его с 0, чтобы система предложила замену")

                # Показываем аллергии
                if result['allergy_issues']:
                    with st.expander("Аллергены в рецепте"):
                        for a in result['allergy_issues']:
                            st.write(f"• {a['name']} содержит аллерген: {a['allergen']}")
                        st.info("💡 В разделе 'Другие доступные альтернативы' вы найдете варианты замен без аллергенов")

                # Показываем проблемы с диетой
                if result['diet_issues']:
                    with st.expander("Проблемы с диетой"):
                        for d in result['diet_issues']:
                            st.write(f"• {d['name']} не соответствует диете {d['diet']}")
                        st.info("💡 В разделе 'Другие доступные альтернативы' вы найдете варианты замен")

                # Показываем произведенные замены
                if result['substitutions']:
                    with st.expander("Произведенные замены"):
                        for sub in result['substitutions']:
                            st.write(f"• **{sub['original']}** → **{sub['alternative']}**")
                            st.caption(f"  Причина: {sub['reason']}")
                            if sub['note']:
                                st.caption(f"  ⓘ {sub['note']}")

                # Показываем другие доступные альтернативы (только для проблемных ингредиентов)
                if result.get('alternatives'):
                    with st.expander("Другие доступные альтернативы"):
                        for alt_group in result['alternatives']:
                            # Показываем только если есть альтернативы, кроме выбранной
                            if len(alt_group['alternatives']) > 1:
                                st.markdown(f"**{alt_group['original']}** → можно заменить на:")
                                for alt in alt_group['alternatives']:
                                    # Пропускаем ту, которая уже была выбрана
                                    is_selected = any(
                                        sub['original'] == alt_group['original'] and sub['alternative'] == alt['name']
                                        for sub in result['substitutions'])
                                    if not is_selected:
                                        confidence_percent = int(alt['confidence'] * 100)
                                        st.markdown(f"  • **{alt['name']}** (уверенность ИИ: {confidence_percent}%)")
                                        if alt['note']:
                                            st.caption(f"    ⓘ {alt['note']}")
                                st.markdown("---")

                # Показываем итоговые ингредиенты
                st.markdown("### Ингредиенты после адаптации:")
                for ing in result['ingredients']:
                    col1, col2, col3 = st.columns([3, 1, 2])
                    with col1:
                        if ing.get('is_substitute'):
                            st.markdown(f"**{ing['name']}** 🔄")
                        elif ing.get('optimized'):
                            st.markdown(f"**{ing['name']}** ⬆️")
                        elif ing.get('limited'):
                            st.markdown(f"**{ing['name']}** ⚠️")
                        else:
                            st.markdown(f"**{ing['name']}**")
                    with col2:
                        st.markdown(f"{ing['quantity']}{ing['unit']}")
                    with col3:
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

with tab2:
    st.header("Добавить новый рецепт в базу")

    with st.form("add_recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("Название рецепта")
        with col2:
            servings_manual = st.number_input(
                "Количество порций",
                min_value=1,
                value=1,
                help="Укажите, на сколько персон рассчитан рецепт. Если не уверены - оставьте 1, система рассчитает автоматически"
            )

        category = st.selectbox(
            "Категория",
            ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"]
        )

        st.subheader("Ингредиенты")
        st.info("Введи каждый ингредиент с новой строки в формате: название количество единица")

        ingredients_text = st.text_area(
            "Ингредиенты",
            placeholder="мука 200г\nяйца 2 шт\nмолоко 100мл\nколбаса 150г\nмайонез 50г",
            height=150
        )

        st.subheader("Шаги приготовления")
        steps_text = st.text_area(
            "Каждый шаг с новой строки",
            placeholder="Нарезать овощи\nДобавить колбасу\nЗаправить майонезом",
            height=150
        )

        col1, col2 = st.columns(2)
        with col1:
            time = st.number_input("Время приготовления (мин)", min_value=5, value=30)
        with col2:
            difficulty = st.selectbox("Сложность", ["легкая", "средняя", "сложная"])

        submitted = st.form_submit_button("Сохранить рецепт", type="primary", use_container_width=True)

        if submitted:
            if recipe_name and ingredients_text:
                ingredients = []
                for line in ingredients_text.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if ',' in line:
                        line = line.replace(',', '')
                    match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(г|мл|шт|ст\.л|ч\.л|кг|л)?', line)
                    if match:
                        ingredients.append({
                            'name': match.group(1).strip().lower(),
                            'quantity': float(match.group(2).replace(',', '.')),
                            'unit': match.group(3) if match.group(3) else 'шт'
                        })
                    else:
                        st.warning(f"Не удалось распознать ингредиент: {line}")

                steps = [s.strip() for s in steps_text.strip().split('\n') if s.strip()]

                if ingredients:
                    new_recipe = {
                        'name': recipe_name,
                        'category': category,
                        'ingredients': ingredients,
                        'steps': steps,
                        'time': time,
                        'difficulty': difficulty,
                        'servings': servings_manual  # Добавляем ручные порции
                    }

                    recipe_id = adapter.manager.add_recipe(new_recipe)
                    st.success(f"Рецепт '{recipe_name}' добавлен в базу!")

                    # Переключаемся на вкладку с рецептами
                    st.session_state.active_tab = 0
                    st.rerun()
                else:
                    st.error("Не удалось распознать ингредиенты! Проверь формат.")
            else:
                st.error("Заполни название и ингредиенты!")

st.markdown("---")
st.markdown(
    "<center>Умный адаптер рецептов — курсовая работа по ИИ</center>",
    unsafe_allow_html=True
)
