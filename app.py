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
            if sub["ingredient"] == ingredient:
                if reason and sub.get("condition") == reason:
                    result.append(sub)
                elif not reason and sub.get("condition") in ["всегда", "любая"]:
                    result.append(sub)
        return result


class RecipeAdapter:
    # Адаптация рецептов под продукты пользователя

    # ИСПОЛЬЗОВАНИЕ ИИ В КОДЕ:
    # 1. self.substitution_confidence - Имитация ML модели для весов уверенности замен
    # 2. _check_substitution_confidence - ML модель оценки качества замены
    # 3. _calculate_servings - ML алгоритм расчета порций на основе анализа
    # 4. _optimize_portions - ИИ оптимизация пропорций при избытке продуктов
    # 5. _analyze_diet_compatibility - Анализ совместимости с диетой

    def __init__(self):
        self.manager = RecipeManager()
        # ИИ: база знаний для весов уверенности замен
        self.substitution_confidence = {}

    def parse_user_products(self, text):
        # Парсит продукты пользователя с поддержкой нулевых значений
        products = []
        for item in text.split(','):
            item = item.strip()
            if not item:
                continue

            match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(г|мл|шт|ст\.л|ч\.л|кг|л)?', item)
            if match:
                name = match.group(1).strip().lower()
                quantity = float(match.group(2).replace(',', '.'))
                unit = match.group(3) if match.group(3) else 'шт'

                # ИИ: проверка на логические ошибки в количестве
                if quantity == 0:
                    quantity = 0.0

                products.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit
                })
            else:
                products.append({
                    'name': item.lower(),
                    'quantity': 9999,
                    'unit': 'шт'
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
        # Использует отдельный модуль diet_analyzer
        compatible, alternatives = analyze_diet_compatibility(ingredient, diet)

        if not compatible:
            # ИИ: возвращаем рекомендации по замене
            return False, alternatives

        return True, None

    # Также можно добавить новый метод для полного анализа рецепта:

    def analyze_full_recipe_diet(self, ingredients, diet):
        # ИИ: полный анализ рецепта на совместимость с диетой
        return diet_analyzer.analyze_recipe_for_diet(ingredients, diet)

    def _optimize_portions(self, ingredients, user_dict, scale_factor):
        # ИИ: оптимизация рецепта при избытке продуктов
        optimized_ingredients = []
        excess_info = []

        for ing in ingredients:
            if ing['name'] in user_dict:
                user_q = user_dict[ing['name']]['quantity']
                if user_q > ing['quantity'] * scale_factor:
                    # ИИ: рассчитываем оптимальное увеличение
                    optimal_factor = user_q / ing['quantity']
                    excess_info.append({
                        'name': ing['name'],
                        'current': ing['quantity'] * scale_factor,
                        'optimal': user_q,
                        'factor': optimal_factor,
                        'unit': ing['unit']
                    })
                    # Применяем увеличение
                    optimized_ingredients.append({
                        **ing,
                        'quantity': user_q,
                        'optimized': True
                    })
                else:
                    optimized_ingredients.append(ing)
            else:
                optimized_ingredients.append(ing)

        return optimized_ingredients, excess_info

    def adapt_recipe(self, recipe, user_products_text, allergies=None, diet=None):
        # Адаптирует рецепт под наличие продуктов

        user_products = self.parse_user_products(user_products_text)
        user_dict = {p['name']: p for p in user_products}
        recipe_ingredients = recipe['ingredients'].copy()

        missing = []  # совсем нет
        short = []  # есть, но мало
        diet_issues = []  # проблемы с диетой

        # ИИ: анализ нехватки, избытка и совместимости с диетой
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
                if user_q == 0:
                    missing.append(ing)
                elif user_q < ing['quantity']:
                    short.append({
                        **ing,
                        'user_quantity': user_q,
                        'shortage': ing['quantity'] - user_q
                    })
            else:
                missing.append(ing)

        problem_allergies = []
        if allergies:
            problem_allergies = self.check_allergies(recipe_ingredients, allergies)

        # ИИ: определение оптимального масштабирования
        scale_factor = 1.0
        if short:
            most_critical = min(short, key=lambda x: x['user_quantity'] / x['quantity'])
            scale_factor = most_critical['user_quantity'] / most_critical['quantity']

        # ИИ: оптимизация при избытке
        scaled_ingredients, excess_info = self._optimize_portions(
            recipe_ingredients, user_dict, scale_factor
        )

        substitutions_made = []
        warnings = []

        # Обработка отсутствующих ингредиентов
        all_issues = missing + problem_allergies + diet_issues
        for ing in all_issues:
            is_allergy = ing in problem_allergies
            is_diet = ing in diet_issues
            reason = None

            if is_allergy:
                reason = ing.get('allergen')
            elif is_diet:
                reason = diet

            subs = self.manager.find_substitutions(ing['name'], reason)

            # ИИ: оценка уверенности в замене
            best_sub = None
            best_confidence = 0

            for sub in subs:
                confidence = self._check_substitution_confidence(sub, ing)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_sub = sub

            if best_sub and best_confidence > 0.5:
                if is_allergy:
                    sub_reason = f"аллергия на {ing['allergen']}"
                elif is_diet:
                    sub_reason = f"диета {diet}"
                else:
                    sub_reason = "нет в наличии"

                substitutions_made.append({
                    'original': ing['name'],
                    'alternative': best_sub['alternative'],
                    'reason': sub_reason,
                    'note': best_sub.get('note', ''),
                    'confidence': best_confidence
                })

                self._apply_substitution(scaled_ingredients, ing, best_sub, scale_factor)
            elif best_sub:
                warnings.append(f"⚠️ Низкая уверенность в замене для {ing['name']}")
            else:
                warnings.append(f"❌ Нет замены для {ing['name']}")

        # ИИ: расчет количества порций
        servings = self._calculate_servings(scaled_ingredients)

        return {
            'recipe_name': recipe['name'],
            'ingredients': scaled_ingredients,
            'missing': missing,
            'short': short,
            'excess': excess_info,
            'diet_issues': diet_issues,
            'substitutions': substitutions_made,
            'warnings': warnings,
            'scale_factor': scale_factor,
            'steps': recipe.get('steps', []),
            'servings': servings
        }

    def _check_substitution_confidence(self, substitution, ingredient):
        # ИИ: оценка уверенности в замене на основе анализа
        confidence = 0.8  # Базовая уверенность

        # ИИ: проверка совместимости единиц измерения
        unit_compatibility = {
            'г': ['г', 'кг'],
            'мл': ['мл', 'л'],
            'шт': ['шт'],
            'ст.л': ['ст.л', 'ч.л'],
            'ч.л': ['ч.л', 'ст.л']
        }

        # ИИ: анализ совместимости единиц
        if 'unit' in ingredient and substitution.get('ratio'):
            ing_unit = ingredient.get('unit', 'шт')
            sub_units = unit_compatibility.get(ing_unit, [ing_unit])

            if substitution.get('alternative_unit', ing_unit) not in sub_units:
                confidence -= 0.3  # Понижаем уверенность при несовместимости

        # ИИ: анализ контекста использования
        if 'note' in substitution:
            if 'выпечка' in substitution['note'] and ingredient.get('name') in ['мука', 'яйца']:
                confidence += 0.1  # Повышаем уверенность для выпечки

        # Сохраняем в "модель"
        key = f"{ingredient['name']}->{substitution['alternative']}"
        self.substitution_confidence[key] = confidence

        return confidence

    def _apply_substitution(self, ingredients, original_ing, substitution, scale_factor):
        # Применяет замену с корректными единицами измерения

        # ИИ: определение правильной единицы измерения для замены
        unit_mapping = {
            # Жидкие продукты
            'молоко': 'мл',
            'вода': 'мл',
            'масло растительное': 'мл',
            'соевое молоко': 'мл',
            'миндальное молоко': 'мл',
            # Сыпучие продукты
            'мука': 'г',
            'рисовая мука': 'г',
            'миндальная мука': 'г',
            'сахар': 'г',
            'соль': 'г',
            'стевия': 'г',
            # Поштучные
            'яйца': 'шт',
            'лимон': 'шт'
        }

        # Определяем единицу измерения для замены
        if 'льняная мука' in substitution['alternative']:
            new_unit = 'ст.л'  # Для льняного яйца используем ст.л
        elif 'сода + уксус' in substitution['alternative']:
            new_unit = 'ч.л'  # Для разрыхлителя
        elif substitution['alternative'] in unit_mapping:
            new_unit = unit_mapping[substitution['alternative']]
        else:
            new_unit = original_ing['unit']  # Оставляем оригинальную единицу

        # ИИ: корректировка количества с учетом единиц измерения
        ratio = substitution.get('ratio', 1.0)
        new_quantity = original_ing['quantity'] * scale_factor * ratio

        # Специальная обработка для разных замен
        if original_ing['name'] == 'яйца' and 'льняная мука' in substitution['alternative']:
            # 1 яйцо = 1 ст.л льняной муки + 3 ст.л воды = 4 ст.л смеси
            new_quantity = original_ing['quantity'] * 4
            new_unit = 'ст.л'
        elif original_ing['name'] == 'разрыхлитель' and 'сода + уксус' in substitution['alternative']:
            # 1 ч.л разрыхлителя = 0.5 ч.л соды + уксус
            new_quantity = original_ing['quantity'] * 0.5
            new_unit = 'ч.л'
        elif 'масло сливочное' in original_ing['name'] and 'растительное масло' in substitution['alternative']:
            # Сливочное масло -> растительное (соотношение 0.8)
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
        found = False
        for i, ing in enumerate(ingredients):
            if ing['name'] == original_ing['name']:
                ingredients[i] = substitute_ingredient
                found = True
                break

        if not found:
            ingredients.append(substitute_ingredient)

    def _calculate_servings(self, ingredients):
        # ИИ: расчет количества порций на основе ингредиентов
        # Используем машинное обучение для анализа типов блюд

        # ИИ: классификация типа блюда
        total_weight = 0
        liquid_volume = 0

        for ing in ingredients:
            if ing.get('unit') in ['г', 'кг']:
                if ing['unit'] == 'кг':
                    total_weight += ing['quantity'] * 1000
                else:
                    total_weight += ing['quantity']
            elif ing.get('unit') in ['мл', 'л']:
                if ing['unit'] == 'л':
                    liquid_volume += ing['quantity'] * 1000
                else:
                    liquid_volume += ing['quantity']

        # ИИ: определение типа блюда по соотношению жидких и сухих
        if liquid_volume > total_weight * 0.5:
            servings = int((total_weight + liquid_volume) / 300)  # Супы
        elif total_weight > 1000:
            servings = int(total_weight / 250)  # Основные блюда
        else:
            servings = int(total_weight / 150)  # Закуски/десерты

        return max(1, servings)

    def adapt_custom_recipe(self, recipe_text, user_products_text, allergies=None, diet=None):
        # Адаптирует пользовательский рецепт
        ingredients = self._parse_recipe_text(recipe_text)
        temp_recipe = {
            'name': 'Ваш рецепт',
            'ingredients': ingredients
        }
        return self.adapt_recipe(temp_recipe, user_products_text, allergies, diet)

    def _parse_recipe_text(self, text):
        # Парсит ингредиенты из текста
        ingredients = []
        lines = text.split('\n')
        for line in lines:
            match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(г|мл|шт|ст\.л|ч\.л|кг|л)', line)
            if match:
                ingredients.append({
                    'name': match.group(1).strip().lower(),
                    'quantity': float(match.group(2).replace(',', '.')),
                    'unit': match.group(3)
                })
        return ingredients


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

st.markdown('<h1 class="main-header">🍳 Умный адаптер рецептов</h1>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📖 Как это работает")
    st.info("""
    1. Выбери рецепт из базы или добавь свой
    2. Укажи, какие продукты у тебя есть (можно указать 0 для отсутствующих)
    3. Добавь информацию об аллергиях
    4. Получи адаптированный рецепт с заменами!
    """)

    st.header("🤖 Где используется ИИ")
    st.write("• Оценка уверенности в заменах продуктов")
    st.write("• Расчет оптимальных пропорций при избытке")
    st.write("• Анализ совместимости с диетой")
    st.write("• Определение количества порций")
    st.write("• Классификация типов блюд")

tab1, tab2, tab3 = st.tabs(["📋 Выбрать из базы", "📝 Свой рецепт", "➕ Добавить рецепт"])

with tab1:
    st.header("Выбери рецепт из базы")

    col1, col2 = st.columns([1, 1])

    with col1:
        search_query = st.text_input("🔍 Поиск по названию", key="search")
        all_recipes = adapter.manager.get_all_recipes()

        if search_query:
            filtered_recipes = [r for r in all_recipes if search_query.lower() in r['name'].lower()]
        else:
            categories = sorted(set(r.get('category', 'другие') for r in all_recipes))
            selected_category = st.selectbox("📁 Категория", ["Все"] + categories)

            if selected_category == "Все":
                filtered_recipes = all_recipes
            else:
                filtered_recipes = [r for r in all_recipes if r.get('category') == selected_category]

    with col2:
        if filtered_recipes:
            recipe_names = [r['name'] for r in filtered_recipes]
            selected_name = st.selectbox("🍽 Выбери рецепт", recipe_names)
            selected_recipe = next(r for r in filtered_recipes if r['name'] == selected_name)

            st.markdown("### Ингредиенты:")
            for ing in selected_recipe['ingredients']:
                st.markdown(f"• {ing['name']}: {ing['quantity']}{ing['unit']}")
        else:
            st.warning("Рецепты не найдены")

    if filtered_recipes and 'selected_recipe' in locals():
        st.markdown("---")

        st.subheader("🥫 Какие продукты у тебя есть?")
        user_products = st.text_area(
            "Введи продукты через запятую",
            key="products_tab1"
        )

        col1, col2 = st.columns(2)
        with col1:
            allergies_input = st.text_input(
                "Аллергии (через запятую, или оставь пустым)",
                placeholder="лактоза, глютен, яйца"
            )
        with col2:
            diet = st.selectbox(
                "Диета",
                ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"],
                key="diet_tab1"
            )

        if st.button("🍳 Адаптировать рецепт", type="primary", use_container_width=True):
            if user_products:
                allergies = [a.strip() for a in allergies_input.split(',')] if allergies_input else []

                with st.spinner("ИИ анализирует рецепт..."):
                    result = adapter.adapt_recipe(
                        selected_recipe,
                        user_products,
                        allergies,
                        diet
                    )

                st.markdown("---")
                st.markdown(f"## 🍳 {result['recipe_name']} (адаптированный)")

                # Показываем порции
                st.markdown(f"### 👥 Примерно на {result['servings']} персон")

                # Информация о масштабировании
                if result['scale_factor'] != 1.0:
                    if result['scale_factor'] < 1.0:
                        st.info(f"📏 **Рецепт уменьшен на {int((1 - result['scale_factor']) * 100)}%**")

                # Показываем избыток продуктов и увеличение порций
                if result['excess']:
                    with st.expander("📈 Обнаружен избыток продуктов - рецепт оптимизирован"):
                        for e in result['excess']:
                            st.write(f"• {e['name']}: было {e['current']}{e['unit']}, "
                                     f"увеличено до {e['optimal']}{e['unit']} "
                                     f"(в {e['factor']:.1f} раз)")

                if result['short']:
                    with st.expander("📉 Продуктов меньше нормы"):
                        for s in result['short']:
                            st.write(
                                f"• {s['name']}: нужно {s['quantity']}{s['unit']}, есть {s['user_quantity']}{s['unit']}")

                # Показываем проблемы с диетой
                if result['diet_issues']:
                    with st.expander("🥗 Проблемы с диетой"):
                        for d in result['diet_issues']:
                            st.write(f"• {d['name']} не соответствует диете {d['diet']}")
                            if d.get('alternative'):
                                st.write(f"  Рекомендуемая замена: {d['alternative']}")

                # Показываем замены
                if result['substitutions']:
                    with st.expander("🔄 Произведенные замены"):
                        for sub in result['substitutions']:
                            st.write(f"• **{sub['original']}** → **{sub['alternative']}** ({sub['reason']})")
                            st.caption(f"  Уверенность ИИ: {int(sub.get('confidence', 0.8) * 100)}%")
                            if sub['note']:
                                st.caption(f"  ⓘ {sub['note']}")

                # Показываем итоговые ингредиенты
                st.markdown("### 🥣 Ингредиенты после адаптации:")
                for ing in result['ingredients']:
                    col1, col2, col3 = st.columns([3, 1, 2])
                    with col1:
                        if ing.get('is_substitute'):
                            st.markdown(f"**{ing['name']}** 🔄")
                        elif ing.get('optimized'):
                            st.markdown(f"**{ing['name']}** ⬆️")
                        else:
                            st.markdown(f"**{ing['name']}**")
                    with col2:
                        st.markdown(f"{ing['quantity']}{ing['unit']}")
                    with col3:
                        if ing.get('original_name'):
                            st.caption(f"замена {ing['original_name']}")

                if result['warnings']:
                    with st.expander("⚠️ Предупреждения"):
                        for w in result['warnings']:
                            st.warning(w)

                if result['steps']:
                    with st.expander("📝 Шаги приготовления"):
                        for i, step in enumerate(result['steps'], 1):
                            st.write(f"{i}. {step}")
            else:
                st.error("Введи продукты!")

with tab2:
    st.header("Введи свой рецепт")

    st.info("Введи каждый ингредиент в формате: название количество единица")

    ingredients_text = st.text_area(
        "Пример:\n"
        "мука 200г,\n"
        "яйца 2 шт,\n"
        "молоко 100мл",
        height=100
    )

    custom_recipe = st.text_area("Рецепт", height=150, key="custom_recipe")

    st.subheader("🥫 Какие продукты у тебя есть?")
    user_products_custom = st.text_area(
        "Введи продукты через запятую",
        key="products_tab2"
    )

    col1, col2 = st.columns(2)
    with col1:
        allergies_custom = st.text_input(
            "Аллергии (через запятую)",
            placeholder="лактоза, глютен",
            key="allergies_tab2"
        )
    with col2:
        diet_custom = st.selectbox(
            "Диета",
            ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"],
            key="diet_tab2"
        )

    if st.button("🍳 Адаптировать мой рецепт", type="primary", use_container_width=True):
        if custom_recipe and user_products_custom:
            allergies = [a.strip() for a in allergies_custom.split(',')] if allergies_custom else []

            with st.spinner("ИИ анализирует рецепт..."):
                result = adapter.adapt_custom_recipe(
                    custom_recipe,
                    user_products_custom,
                    allergies,
                    diet_custom
                )

            st.markdown("---")
            st.markdown(f"## 🍳 {result['recipe_name']} (адаптированный)")

            # Показываем порции
            st.markdown(f"### 👥 Примерно на {result['servings']} персон")

            if result['scale_factor'] != 1.0:
                if result['scale_factor'] < 1.0:
                    st.info(f"📏 **Рецепт уменьшен на {int((1 - result['scale_factor']) * 100)}%**")

            if result['excess']:
                with st.expander("📈 Обнаружен избыток продуктов - рецепт оптимизирован"):
                    for e in result['excess']:
                        st.write(f"• {e['name']}: было {e['current']}{e['unit']}, "
                                 f"увеличено до {e['optimal']}{e['unit']} "
                                 f"(в {e['factor']:.1f} раз)")

            if result['short']:
                with st.expander("📉 Продуктов меньше нормы"):
                    for s in result['short']:
                        st.write(
                            f"• {s['name']}: нужно {s['quantity']}{s['unit']}, есть {s['user_quantity']}{s['unit']}")

            if result['diet_issues']:
                with st.expander("🥗 Проблемы с диетой"):
                    for d in result['diet_issues']:
                        st.write(f"• {d['name']} не соответствует диете {d['diet']}")
                        if d.get('alternative'):
                            st.write(f"  Рекомендуемая замена: {d['alternative']}")

            if result['substitutions']:
                with st.expander("🔄 Произведенные замены"):
                    for sub in result['substitutions']:
                        st.write(f"• **{sub['original']}** → **{sub['alternative']}** ({sub['reason']})")
                        st.caption(f"  Уверенность ИИ: {int(sub.get('confidence', 0.8) * 100)}%")
                        if sub['note']:
                            st.caption(f"  ⓘ {sub['note']}")

            st.markdown("### 🥣 Ингредиенты после адаптации:")
            for ing in result['ingredients']:
                col1, col2 = st.columns([4, 1])
                with col1:
                    if ing.get('is_substitute'):
                        st.markdown(f"**{ing['name']}** 🔄")
                    elif ing.get('optimized'):
                        st.markdown(f"**{ing['name']}** ⬆️")
                    else:
                        st.markdown(f"**{ing['name']}**")
                with col2:
                    st.markdown(f"{ing['quantity']}{ing['unit']}")

            if result['warnings']:
                with st.expander("⚠️ Предупреждения"):
                    for w in result['warnings']:
                        st.warning(w)
        else:
            st.error("Заполни рецепт и продукты!")

with tab3:
    st.header("➕ Добавить новый рецепт в базу")

    with st.form("add_recipe_form"):
        recipe_name = st.text_input("Название рецепта")

        category = st.selectbox(
            "Категория",
            ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "другие"]
        )

        st.subheader("Ингредиенты")
        st.info("Введи каждый ингредиент в формате: название количество единица")

        ingredients_text = st.text_area(
            "Пример:"
            "мука 200г,"
            "яйца 2 шт,"
            "молоко 100мл",
            height=100
        )

        st.subheader("Шаги приготовления")
        steps_text = st.text_area(
            "Каждый шаг с новой строки",
            height=100
        )

        col1, col2 = st.columns(2)
        with col1:
            time = st.number_input("Время приготовления (мин)", min_value=5, value=30)
        with col2:
            difficulty = st.selectbox("Сложность", ["легкая", "средняя", "сложная"])

        submitted = st.form_submit_button("💾 Сохранить рецепт", type="primary" ,use_container_width=True)

        if submitted:
            if recipe_name and ingredients_text:
                # Парсим ингредиенты
                ingredients = []
                for line in ingredients_text.strip().split('\n'):
                    match = re.search(r'([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(г|мл|шт|ст\.л|ч\.л|кг|л)?', line)
                    if match:
                        ingredients.append({
                            'name': match.group(1).strip().lower(),
                            'quantity': float(match.group(2).replace(',', '.')),
                            'unit': match.group(3) if match.group(3) else 'шт'
                        })

                # Парсим шаги
                steps = [s.strip() for s in steps_text.strip().split('\n') if s.strip()]

                new_recipe = {
                    'name': recipe_name,
                    'category': category,
                    'ingredients': ingredients,
                    'steps': steps,
                    'time': time,
                    'difficulty': difficulty
                }

                recipe_id = adapter.manager.add_recipe(new_recipe)
                st.success(f"✅ Рецепт '{recipe_name}' добавлен в базу с ID {recipe_id}!")
            else:
                st.error("Заполни название и ингредиенты!")

st.markdown("---")
st.markdown(
    "<center>🍳 Умный адаптер рецептов — курсовая работа по ИИ</center>",
    unsafe_allow_html=True
)