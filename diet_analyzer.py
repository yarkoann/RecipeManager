# Модуль для анализа совместимости ингредиентов с диетами
# ИСПОЛЬЗОВАНИЕ ИИ: анализ пищевых ограничений и поиск альтернатив

class DietAnalyzer:
    # Анализатор совместимости продуктов с различными диетами
    # ИИ: база знаний о диетах и продуктах

    def __init__(self):
        # ИИ: база знаний ограничений для разных диет

        self.diet_restrictions = {
            "Кето": {
                "запрещено": [
                    "сахар", "мука", "фрукты", "крупы",
                    "хлеб", "макароны", "картофель", "рис",
                    "банан", "виноград", "сладкие фрукты"
                ],
                "разрешено": [
                    "мясо", "рыба", "яйца", "сыр",
                    "орехи", "авокадо", "растительное масло",
                    "сливочное масло", "сливки"
                ]
            },


            "Веган": {
                "запрещено": [
                    "молоко", "яйца", "масло сливочное", "творог",
                    "сыр", "кефир", "йогурт", "сметана", "сливки",
                    "мед", "желатин", "курица", "говядина", "рыба"
                ],
                "разрешено": [
                    "овощи", "фрукты", "орехи", "бобовые",
                    "растительное масло", "тофу", "соевое молоко",
                    "миндальное молоко", "кокосовое молоко"
                ]
            },


            "Вегетарианец": {
                "запрещено": [
                    "мясо", "рыба", "курица", "говядина",
                    "свинина", "морепродукты"
                ],
                "разрешено": [
                    "молоко", "яйца", "сыр", "творог",
                    "овощи", "фрукты", "орехи"
                ]
            },


            "Без сахара": {
                "запрещено": [
                    "сахар", "мед", "кленовый сироп", "патока",
                    "конфеты", "шоколад", "варенье", "джем",
                    "сладкие газировки", "соки с сахаром"
                ],
                "разрешено": [
                    "стевия", "эритрит", "фрукты в умеренных количествах"
                ]
            },



            "без глютена": {
                "запрещено": [
                    "мука пшеничная", "мука ржаная", "мука ячменная",
                    "манка", "кус-кус", "булгур", "пшеница"
                ],
                "разрешено": [
                    "рисовая мука", "кукурузная мука", "гречневая мука",
                    "миндальная мука", "кокосовая мука", "овсяная мука"
                ]
            },
            "лактоза": {
                "запрещено": [
                    "молоко", "сливки", "сметана", "йогурт",
                    "творог", "сыр мягкий", "кефир", "масло сливочное"
                ],
                "разрешено": [
                    "безлактозное молоко", "соевое молоко",
                    "миндальное молоко", "кокосовое молоко",
                    "растительное масло", "тофу"
                ]
            }
        }

        # ИИ: база знаний альтернатив для запрещенных продуктов
        self.alternatives_database = {
            "сахар": {
                "стевия": "1 ч.л сахара = щепотка стевии",
                "эритрит": "1:1.3 (эритрита нужно в 1.3 раза больше)",
                "сироп топинамбура": "1:1",
                "финики измельченные": "100г сахара = 150г фиников"
            },
            "мука": {
                "миндальная мука": "1:1 (подходит для кето)",
                "рисовая мука": "1:1 (без глютена)",
                "кокосовая мука": "1:0.3 + добавить яйцо",
                "гречневая мука": "1:1 (без глютена)"
            },
            "молоко": {
                "соевое молоко": "1:1 (веган)",
                "миндальное молоко": "1:1 (веган, кето)",
                "кокосовое молоко": "1:0.7 (веган, кето)",
                "овсяное молоко": "1:1 (веган)"
            },
            "яйца": {
                "льняное яйцо": "1 яйцо = 1ст.л муки + 3ст.л воды (веган)",
                "банан": "1 яйцо = 0.5 банана (для выпечки, веган)",
                "аквафаба": "1 яйцо = 3ст.л жидкости от нута (веган)"
            },
            "масло сливочное": {
                "растительное масло": "100г = 80мл (веган, кето)",
                "кокосовое масло": "1:1 (веган, кето)",
                "оливковое масло": "1:0.9 (веган, кето)"
            },
            "творог": {
                "тофу": "1:1 (веган)",
                "кокосовый творог": "1:1 (веган, кето)",
                "сыр тофу": "1:1 (веган)"
            },
            "сыр": {
                "тофу": "1:1 (веган)",
                "кокосовый сыр": "1:1 (веган, кето)",
                "ореховый сыр": "1:1 (веган)"
            },
            "мед": {
                "кленовый сироп": "1:1 (веган)",
                "сироп агавы": "1:1 (веган)",
                "стевия": "по вкусу (веган, кето)"
            },
            "картофель": {
                "цветная капуста": "1:1 (кето)",
                "брокколи": "1:1 (кето)",
                "кабачки": "1:1 (кето)"
            },
            "рис": {
                "цветная капуста": "измельченная, 1:1 (кето)",
                "киноа": "1:1 (умеренно)",
                "гречка": "1:1"
            }
        }

        # ИИ: маппинг продуктов на категории для умного поиска
        self.product_categories = {
            "молоко": "молочные",
            "яйца": "яйца",
            "масло сливочное": "молочные",
            "творог": "молочные",
            "сыр": "молочные",
            "сахар": "подсластители",
            "мед": "подсластители",
            "мука": "мучные",
            "мясо": "мясные",
            "рыба": "рыбные",
            "картофель": "овощи крахмалистые",
            "рис": "крупы",
            "фрукты": "фрукты"
        }

    def check_compatibility(self, ingredient, diet):
        # ИИ: проверка совместимости ингредиента с диетой
        # Возвращает (совместим, причина, альтернативы)

        if not diet or diet == "Нет":
            return True, None, None

        ing_name = ingredient['name'].lower()

        # Ищем в базе ограничений
        if diet in self.diet_restrictions:
            restrictions = self.diet_restrictions[diet]

            # Проверяем по точному совпадению
            if 'запрещено' in restrictions:
                for forbidden in restrictions['запрещено']:
                    # Проверяем вхождение (чтобы найти "мука" в "мука пшеничная")
                    if forbidden.lower() in ing_name or ing_name in forbidden.lower():
                        # ИИ: ищем альтернативы
                        alternatives = self.find_alternatives(ing_name, diet)
                        return False, f"Запрещено на диете {diet}", alternatives

        return True, None, None

    def find_alternatives(self, ingredient_name, diet=None):
        # ИИ: поиск альтернатив для ингредиента с учетом диеты
        alternatives = []

        # Ищем в базе альтернатив
        for key, alts in self.alternatives_database.items():
            if key in ingredient_name or ingredient_name in key:
                for alt_name, alt_desc in alts.items():
                    # Проверяем, подходит ли альтернатива для диеты
                    if diet:
                        # Быстрая проверка совместимости альтернативы с диетой
                        alt_compatible = True

                        # Проверяем, не запрещена ли альтернатива на этой диете
                        if diet in self.diet_restrictions:
                            restrictions = self.diet_restrictions[diet]
                            if 'запрещено' in restrictions:
                                for forbidden in restrictions['запрещено']:
                                    if forbidden.lower() in alt_name.lower():
                                        alt_compatible = False
                                        break

                        if alt_compatible:
                            alternatives.append({
                                'name': alt_name,
                                'description': alt_desc,
                                'type': 'прямая замена'
                            })
                    else:
                        alternatives.append({
                            'name': alt_name,
                            'description': alt_desc,
                            'type': 'прямая замена'
                        })

        # Если нет прямых замен, ищем по категориям
        if not alternatives:
            category_alts = self._find_by_category(ingredient_name, diet)
            alternatives.extend(category_alts)

        # ИИ: сортировка по релевантности
        alternatives = self._rank_alternatives(alternatives, ingredient_name)

        return alternatives

    def _find_by_category(self, ingredient_name, diet):
        # ИИ: поиск альтернатив по категории продукта
        alternatives = []

        # Определяем категорию продукта
        category = None
        for prod, cat in self.product_categories.items():
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
            # Фильтруем по диете
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

            # Повышаем score для прямых замен
            if alt.get('type') == 'прямая замена':
                score += 20

            # Понижаем для менее точных
            if alt.get('type') == 'категория':
                score -= 10

            # Повышаем для альтернатив, которые явно подходят под диету
            if 'кето' in alt.get('description', '') or 'веган' in alt.get('description', ''):
                score += 15

            alt['relevance_score'] = score
            ranked.append(alt)

        # Сортируем по score
        return sorted(ranked, key=lambda x: x['relevance_score'], reverse=True)

    def get_diet_info(self, diet):
        # Возвращает информацию о диете
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
    # Обертка для вызова из основного кода
    analyzer = DietAnalyzer()
    compatible, reason, alternatives = analyzer.check_compatibility(ingredient, diet)

    if not compatible and alternatives:
        # Формируем строку с альтернативами
        alt_text = " | ".join([f"{a['name']} ({a['description']})" for a in alternatives[:2]])
        return False, alt_text

    return compatible, None


# Инициализация глобального экземпляра для использования
diet_analyzer = DietAnalyzer()