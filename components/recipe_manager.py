"""
RecipeManager — операции CRUD с базой данных рецептов и ингредиентов.
"""
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

    # components/recipe_manager.py — улучшенный search_by_available_ingredients

    def search_by_available_ingredients(self, user_products: list) -> list:
        """Умный поиск: находит рецепты с учётом синонимов и групп продуктов."""
        # Расширяем список продуктов пользователя с учётом синонимов
        expanded_user_products = []
        for p in user_products:
            name = p.get('name', '').lower()
            expanded_user_products.append(name)

            # Добавляем синонимы через RecipeAdapter (нужен доступ)
            # Для простоты — добавим базовые группы прямо здесь
            synonym_groups = {
                "сыр": ["пармезан", "моцарелла", "чеддер", "рикотта", "фета", "брынза", "гауда"],
                "помидор": ["томат", "томаты", "черри"],
                "мука": ["мука пшеничная", "пшеничная мука"],
                "картофель": ["картошка"],
                "гречка": ["гречневая крупа", "греча"],
                "овсянка": ["овсяные хлопья"],
            }

            for group, members in synonym_groups.items():
                if name == group or name in members:
                    expanded_user_products.append(group)
                    expanded_user_products.extend(members)
                elif name in [group] + members:
                    expanded_user_products.append(group)
                    expanded_user_products.extend(members)

        user_names = set(expanded_user_products)

        results = []
        for recipe in self.recipes:
            required = [
                ing for ing in recipe.get('ingredients', [])
                if not ing.get('by_taste') and ing.get('quantity') is not None
            ]
            if not required:
                continue

            matched = 0
            for ing in required:
                ing_name = ing['name'].lower()
                # Проверяем совпадение:
                # - точное совпадение
                # - ингредиент пользователя содержит название из рецепта
                # - название из рецепта содержит ингредиент пользователя
                # - через группы синонимов
                found = False
                for user_name in user_names:
                    if ing_name == user_name or user_name in ing_name or ing_name in user_name:
                        found = True
                        break
                if found:
                    matched += 1

            pct = round(matched / len(required) * 100) if required else 0
            results.append({
                'recipe': recipe,
                'matched': matched,
                'total': len(required),
                'pct': pct,
                'missing': len(required) - matched,
            })

        results.sort(key=lambda x: x['pct'], reverse=True)
        return results

    def get_ingredient_info(self, name):
        """Поиск ингредиента по точному совпадению или вхождению подстроки."""
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
