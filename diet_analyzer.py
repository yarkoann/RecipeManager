# Модуль для анализа совместимости ингредиентов с диетами
# ИСПОЛЬЗОВАНИЕ ИИ: анализ пищевых ограничений и поиск альтернатив

import json
import os


class DietAnalyzer:
    # Анализатор совместимости продуктов с различными диетами

    def __init__(self):
        # ИИ: база знаний ограничений для разных диет
        self.diet_restrictions = {
            "Кето": {
                "запрещено": [
                    "сахар", "мука", "фрукты", "крупы",
                    "хлеб", "макароны","морковь", "картофель", "рис",
                    "банан", "виноград", "фрукты",
                    "мед", "конфеты", "сладкое",

                    # Бобовые
                    "фасоль", "чечевица", "горох", "горошек",
                    "нут", "бобы", "соевые бобы", "маш",
                    "кукуруза"
                ],
                "разрешено": [
                    "мясо", "рыба", "яйца", "сыр",
                    "орехи", "авокадо", "растительное масло",
                    "сливочное масло", "сливки", "миндальная мука",
                    "кокосовая мука", "стевия", "эритрит",
                    "грибы", "цветная капуста", "брокколи",
                    "тофу", "семена тыквы", "кабачки", "цукини"
                ]
            },
            "Веган": {
                "запрещено": [
                    "молоко", "яйца", "масло сливочное", "творог",
                    "сыр", "кефир", "йогурт", "сметана", "сливки",
                    "мед", "желатин", "курица", "говядина", "рыба",
                    "мясо", "морепродукты", "майонез", "кетчуп", "колбаса", "сосиски",
                    "ветчина", "бекон"
                ],
                "разрешено": [
                    "овощи", "фрукты", "орехи", "бобовые",
                    "растительное масло", "тофу", "соевое молоко",
                    "миндальное молоко", "кокосовое молоко",
                    "льняная мука", "рисовая мука", "миндальная мука"
                ]
            },
            "Вегетарианец": {
                "запрещено": [
                    "мясо", "рыба", "курица", "говядина",
                    "свинина", "морепродукты", "колбаса",
                    "сосиски", "ветчина", "бекон"
                ],
                "разрешено": [
                    "молоко", "яйца", "сыр", "творог",
                    "овощи", "фрукты", "орехи", "тофу",
                    "сейтан", "бобовые"
                ]
            },
            "Без сахара": {
                "запрещено": [
                    "сахар", "мед", "кленовый сироп", "патока",
                    "конфеты", "шоколад", "варенье", "джем",
                    "сладкие газировки", "майонез", "кетчуп", "соки с сахаром"
                ],
                "разрешено": [
                    "стевия", "эритрит", "фрукты в умеренных количествах"
                ]
            },
            "без глютена": {
                "запрещено": [
                    "мука пшеничная", "мука ржаная", "мука ячменная",
                    "манка", "кус-кус", "булгур", "соевый соус", "пшеница"
                ],
                "разрешено": [
                    "рисовая мука", "кукурузная мука", "гречневая мука",
                    "миндальная мука", "кокосовая мука", "овсяная мука"
                ]
            },
            "лактоза": {
                "запрещено": [
                    "молоко", "сливки", "сметана", "йогурт",
                    "творог", "сыр", "кефир", "масло сливочное",
                    "мороженое"
                ],
                "разрешено": [
                    "безлактозное молоко", "соевое молоко",
                    "миндальное молоко", "кокосовое молоко",
                    "растительное масло", "тофу"
                ]
            }
        }

        # Загружаем замены из substitutions.json
        self.substitutions = self._load_substitutions()

    def _load_substitutions(self):

        try:
            subs_file = "data/substitutions.json"
            if os.path.exists(subs_file):
                with open(subs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("substitutions", [])
            return []
        except:
            return []

    def check_compatibility(self, ingredient, diet):
        # ИИ: проверка совместимости ингредиента с диетой

        if not diet or diet == "Нет":
            return True, None, None

        ing_name = ingredient['name'].lower()

        # Нормализация для консервированных продуктов
        if 'консервированный' in ing_name:
            ing_name = ing_name.replace('консервированный', '').strip()
        if 'консервированная' in ing_name:
            ing_name = ing_name.replace('консервированная', '').strip()
        if 'консервированное' in ing_name:
            ing_name = ing_name.replace('консервированное', '').strip()

        if diet in self.diet_restrictions:
            restrictions = self.diet_restrictions[diet]

            if 'запрещено' in restrictions:
                for forbidden in restrictions['запрещено']:
                    if forbidden.lower() in ing_name or ing_name in forbidden.lower():
                        alternatives = self.find_alternatives(ing_name, diet)
                        return False, f"Запрещено на диете {diet}", alternatives

        return True, None, None

    def find_alternatives(self, ingredient_name, diet=None):
        # ИИ: поиск альтернатив для ингредиента с учетом диеты
        alternatives = []

        # Загружаем substitutions.json
        import json
        import os

        subs_file = "data/substitutions.json"
        if os.path.exists(subs_file):
            with open(subs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                substitutions = data.get("substitutions", [])

                for sub in substitutions:
                    if sub["ingredient"] == ingredient_name:
                        condition = sub.get("condition", "")
                        if diet and condition == diet:
                            alternatives.append({
                                'name': sub['alternative'],
                                'description': sub.get('note', f"Замена: {sub['alternative']}"),
                                'type': 'прямая замена',
                                'ratio': sub.get('ratio', 1.0)
                            })
                        elif not diet and condition in ["всегда", "любая"]:
                            alternatives.append({
                                'name': sub['alternative'],
                                'description': sub.get('note', f"Замена: {sub['alternative']}"),
                                'type': 'прямая замена',
                                'ratio': sub.get('ratio', 1.0)
                            })

        return alternatives

    def _find_by_category(self, ingredient_name, diet):
        # ИИ: поиск альтернатив по категории продукта
        alternatives = []

        product_categories = {
            "молоко": "молочные",
            "яйца": "яйца",
            "масло сливочное": "молочные",
            "творог": "молочные",
            "сыр": "молочные",
            "сливки": "молочные",
            "сметана": "молочные",
            "сахар": "подсластители",
            "мед": "подсластители",
            "мука": "мучные",
            "мясо": "мясные",
            "рыба": "рыбные",
            "картофель": "овощи крахмалистые",
            "рис": "крупы"
        }

        category = None
        for prod, cat in product_categories.items():
            if prod in ingredient_name or ingredient_name in prod:
                category = cat
                break

        if category == "молочные":
            alts = [
                {"name": "соевое молоко", "description": "1:1 (подходит для веган)", "type": "категория"},
                {"name": "миндальное молоко", "description": "1:1 (подходит для веган, кето)", "type": "категория"},
                {"name": "кокосовое молоко", "description": "1:0.7 (подходит для веган, кето)", "type": "категория"},
                {"name": "тофу", "description": "1:1 (для творога/сыра)", "type": "категория"}
            ]
            if diet:
                for alt in alts:
                    alt_compatible = True
                    if diet in self.diet_restrictions:
                        restrictions = self.diet_restrictions[diet]
                        if 'запрещено' in restrictions:
                            for forbidden in restrictions['запрещено']:
                                if forbidden.lower() in alt['name'].lower():
                                    alt_compatible = False
                                    break
                    if alt_compatible:
                        alternatives.append(alt)
            else:
                alternatives = alts

        elif category == "мучные":
            alts = [
                {"name": "миндальная мука", "description": "1:1 (подходит для кето, без глютена)", "type": "категория"},
                {"name": "кокосовая мука", "description": "1:0.3 (подходит для кето, без глютена)",
                 "type": "категория"},
                {"name": "рисовая мука", "description": "1:1 (без глютена)", "type": "категория"},
                {"name": "гречневая мука", "description": "1:1 (без глютена)", "type": "категория"}
            ]
            if diet:
                for alt in alts:
                    alt_compatible = True
                    if diet in self.diet_restrictions:
                        restrictions = self.diet_restrictions[diet]
                        if 'запрещено' in restrictions:
                            for forbidden in restrictions['запрещено']:
                                if forbidden.lower() in alt['name'].lower():
                                    alt_compatible = False
                                    break
                    if alt_compatible:
                        alternatives.append(alt)
            else:
                alternatives = alts

        return alternatives

    def _rank_alternatives(self, alternatives, original_ingredient):
        # ИИ: ранжирование альтернатив по релевантности
        ranked = []
        for alt in alternatives:
            score = 100

            if alt.get('type') == 'прямая замена':
                score += 20

            if alt.get('type') == 'категория':
                score -= 10

            if 'кето' in alt.get('description', '') or 'веган' in alt.get('description', ''):
                score += 15

            alt['relevance_score'] = score
            ranked.append(alt)

        return sorted(ranked, key=lambda x: x['relevance_score'], reverse=True)

    def get_diet_info(self, diet):
        if diet in self.diet_restrictions:
            return self.diet_restrictions[diet]
        return None

    def analyze_recipe_for_diet(self, ingredients, diet):
        # ИИ: полный анализ рецепта на совместимость с диетой
        issues = []
        alternatives_suggested = []

        for ing in ingredients:
            compatible, reason, alternatives = self.check_compatibility(ing, diet)

            if not compatible:
                issues.append({
                    'ingredient': ing['name'],
                    'reason': reason,
                    'alternatives': alternatives[:3] if alternatives else []
                })

                if alternatives:
                    alternatives_suggested.append({
                        'original': ing['name'],
                        'suggested': alternatives[0]['name'],
                        'note': alternatives[0]['description']
                    })

        return {
            'is_compatible': len(issues) == 0,
            'issues': issues,
            'suggestions': alternatives_suggested,
            'diet_name': diet
        }


# Функция для обратной совместимости с основным кодом
def analyze_diet_compatibility(ingredient, diet):
    analyzer = DietAnalyzer()
    compatible, reason, alternatives = analyzer.check_compatibility(ingredient, diet)

    if not compatible and alternatives:
        alt_text = " | ".join([f"{a['name']} ({a['description']})" for a in alternatives[:2]])
        return False, alt_text

    return compatible, None


# Инициализация глобального экземпляра для использования
diet_analyzer = DietAnalyzer()
