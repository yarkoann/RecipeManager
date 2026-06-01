
# RecipeManager — операции CRUD с базой данных рецептов и ингредиентов

import json
import os
from typing import List, Dict, Optional


CAN_GRAMS: Dict[str, int] = {
    "горох": 400, "фасоль": 400, "кукуруза": 340, "нут": 400,
    "чечевица": 400, "томаты": 400, "огурцы": 400, "грибы": 400,
    "оливки": 300, "тунец": 185, "сардины": 185,
}


def can_to_grams(product_name: str, cans: float) -> float:
    return cans * CAN_GRAMS.get(product_name.lower(), 400)


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
        os.makedirs(os.path.dirname(filename), exist_ok=True) if os.path.dirname(filename) else None
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
        for i, recipe in enumerate(self.recipes):
            if recipe.get("id") == recipe_id:
                updated_data["id"] = recipe_id
                self.recipes[i] = updated_data
                self._save_json({"recipes": self.recipes}, self.recipes_file)
                return True
        return False

    def delete_recipe(self, recipe_id: int) -> bool:
        before = len(self.recipes)
        self.recipes = [r for r in self.recipes if r.get("id") != recipe_id]
        if len(self.recipes) < before:
            self._save_json({"recipes": self.recipes}, self.recipes_file)
            return True
        return False

    def search_by_available_ingredients(self, user_products: list) -> list:
        from components.recipe_adapter import RecipeAdapter
        adapter = RecipeAdapter()

        # Расширяем список продуктов пользователя с учётом всех синонимов
        expanded_user_products = set()

        for p in user_products:
            name = p.get('name', '').lower().strip()
            if not name:
                continue

            # Добавляем само имя
            expanded_user_products.add(name)

            # Нормализуем через адаптер (картошка -> картофель, куриное бедро -> курица)
            normalized = adapter.normalize_ingredient_name(name)
            expanded_user_products.add(normalized)

            # Добавляем все синонимы, где это имя является ключом или значением
            for orig, target in adapter.SYNONYM_MAP.items():
                if name == orig or name == target:
                    expanded_user_products.add(orig)
                    expanded_user_products.add(target)
                if normalized == orig or normalized == target:
                    expanded_user_products.add(orig)
                    expanded_user_products.add(target)

            # Добавляем всю группу, если продукт входит в группу
            for group_name, members in adapter.INGREDIENT_GROUPS.items():
                if name == group_name or name in members:
                    expanded_user_products.add(group_name)
                    expanded_user_products.update(members)
                if normalized == group_name or normalized in members:
                    expanded_user_products.add(group_name)
                    expanded_user_products.update(members)

        # Для отладки - можно посмотреть в st.sidebar
        # st.sidebar.write(f"Расширенные продукты: {expanded_user_products}")

        results = []
        for recipe in self.recipes:
            # Собираем обязательные ингредиенты (не "по вкусу")
            required = [
                ing for ing in recipe.get('ingredients', [])
                if not ing.get('by_taste') and ing.get('quantity') is not None
            ]
            if not required:
                continue

            matched = 0
            matched_names = []
            missing_names = []

            for ing in required:
                ing_name = ing['name'].lower().strip()
                # Нормализуем ингредиент рецепта
                ing_normalized = adapter.normalize_ingredient_name(ing_name)

                found = False
                for user_name in expanded_user_products:
                    # Прямое совпадение
                    if ing_name == user_name or ing_normalized == user_name:
                        found = True
                        break
                    # Частичное совпадение (например "лук" в "лук репчатый")
                    if ing_name in user_name or user_name in ing_name:
                        found = True
                        break
                    if ing_normalized in user_name or user_name in ing_normalized:
                        found = True
                        break

                if found:
                    matched += 1
                    matched_names.append(ing_name)
                else:
                    missing_names.append(ing_name)

            if matched > 0:  # Показываем только рецепты, где есть хоть одно совпадение
                pct = round(matched / len(required) * 100) if required else 0
                results.append({
                    'recipe': recipe,
                    'matched': matched,
                    'total': len(required),
                    'pct': pct,
                    'missing': len(required) - matched,
                    'matched_names': matched_names,
                    'missing_names': missing_names,
                })

        # Сортируем по проценту совпадения
        results.sort(key=lambda x: x['pct'], reverse=True)
        return results

    def get_ingredient_info(self, name):

        name_lower = name.lower().strip()
        # Сначала точное совпадение
        exact = next((i for i in self.ingredients if i["name"].lower() == name_lower), None)
        if exact:
            return exact
        # Потом частичное
        return next((i for i in self.ingredients if name_lower in i["name"].lower()
                     or i["name"].lower() in name_lower), None)

    def find_substitutions(self, ingredient, reason=None):
        result = []
        ing_lower = ingredient.lower()
        for sub in self.substitutions:
            sub_ing = sub["ingredient"].lower()
            if sub_ing not in ing_lower and ing_lower not in sub_ing:
                continue
            if reason is None:
                result.append(sub)
            elif reason and sub.get("condition", "").lower() == reason.lower():
                result.append(sub)
            elif not reason and sub.get("condition") in ["всегда", "любая"]:
                result.append(sub)
        return result
