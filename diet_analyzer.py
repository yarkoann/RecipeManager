# Модуль анализа диет с контекстными заменами и оценкой возможности адаптации
import json, os, re

class DishContextClassifier:
    SWEET_KEYWORDS = ["торт","кекс","пирог","пирожное","бисквит","печенье","вафли","суфле","пудинг","маффин","кулич","панкейк","десерт","выпечка"]
    PANCAKE_KEYWORDS = ["блины","оладьи","блинчики","панкейк"]
    SAVORY_KEYWORDS = ["салат","суп","борщ","рагу","котлет","запеканка","плов","жаркое","пельмен","вареник","омлет","яичница","закуска","паштет","окрошка","оливье","винегрет","пицца","паста","ризотто"]
    EGG_DISH_KEYWORDS = ["омлет","яичниц","скрэмбл","яйцо с","глазунья"]

    @classmethod
    def classify(cls, recipe_name, category):
        name_lower = recipe_name.lower()
        cat_lower = (category or "").lower()
        combined = name_lower + " " + cat_lower
        is_sweet = any(k in combined for k in cls.SWEET_KEYWORDS + ["десерт","выпечка"])
        is_pancake = any(k in combined for k in cls.PANCAKE_KEYWORDS)
        is_savory = any(k in combined for k in cls.SAVORY_KEYWORDS)
        is_egg_dish = any(k in combined for k in cls.EGG_DISH_KEYWORDS)
        if is_egg_dish:
            egg_role = "egg_dish"
        elif is_sweet or is_pancake:
            egg_role = "leavening"
        elif any(k in combined for k in ["котлет","тефтел","фарш","запеканк","пельмен"]):
            egg_role = "binder"
        elif any(k in combined for k in ["салат","оливье","винегрет","закуска","окрошк"]):
            egg_role = "garnish"
        else:
            egg_role = "general"
        return {"is_sweet":is_sweet,"is_pancake":is_pancake,"is_savory":is_savory,
                "is_egg_dish":is_egg_dish,"egg_role":egg_role,"name_lower":name_lower,"category":cat_lower}

    @classmethod
    def egg_role_label(cls, role):
        labels = {"egg_dish":"🍳 Яйца — основа блюда (омлет/яичница)","leavening":"🧁 Яйца — разрыхлитель/структура в выпечке",
                  "binder":"🥩 Яйца — связующий агент (котлеты/фарш)","garnish":"🥗 Яйца — компонент несладкого блюда/салата","general":""}
        return labels.get(role,"")


class AdaptationFeasibilityChecker:
    IMPOSSIBLE_SUBSTITUTIONS = {
        ("яйца","garnish"): {"bad_subs":["банан","банан (пюре)","аквафаба"],"reason":"Банан и аквафаба несовместимы с несладким блюдом"},
        ("яйца","leavening"): {"bad_subs":["тофу (плотный)","нут отварной","авокадо"],"reason":"Тофу и нут не дают нужной структуры в выпечке"},
    }
    ALTERNATIVE_DISHES = {
        "egg_dish":[{"name":"Веган-омлет из нутовой муки","note":"4 ст.л. нутовой муки + 100 мл воды + куркума + специи"},
                    {"name":"Тофу-скрэмбл","note":"150 г мягкого тофу + куркума + соль — жарить как яичницу"},
                    {"name":"Овощная запеканка","note":"Кабачок, помидоры, лук — без яиц"}],
        "garnish":[{"name":"Салат с нутом","note":"Заменить яйца в оливье на нут отварной"},
                   {"name":"Салат с авокадо","note":"Авокадо вместо яиц — кремовая текстура"},
                   {"name":"Веган-оливье с тофу","note":"Маринованный тофу вместо яиц и колбасы"}],
        "leavening":[{"name":"Банановые панкейки","note":"Банан + овсянка + растительное молоко — без яиц"},
                     {"name":"Льняные блины","note":"Льняная мука + вода вместо яиц"},
                     {"name":"Нутовые вафли","note":"Нутовая мука + вода + специи"}],
        "binder":[{"name":"Котлеты из чечевицы","note":"Чечевица + морковь + специи — без яиц"},
                  {"name":"Фалафель","note":"Нут + специи — жарить или запекать"}],
        "general":[{"name":"Веган-версия этого блюда","note":"Замените все проблемные ингредиенты растительными"}],
    }

    @classmethod
    def check(cls, recipe, issues, dish_context):
        warnings, alternative_dishes, impossible_reasons = [], [], []
        egg_role = dish_context.get("egg_role","general")
        for issue in issues:
            ing_name = issue.get("name", issue.get("ingredient",""))
            planned_sub = issue.get("best_sub_name","")
            key = (ing_name, egg_role)
            if key in cls.IMPOSSIBLE_SUBSTITUTIONS:
                bad = cls.IMPOSSIBLE_SUBSTITUTIONS[key]
                if planned_sub in bad["bad_subs"]:
                    impossible_reasons.append(f"❌ {ing_name}: {bad['reason']}")
            if ing_name == "яйца" and egg_role == "egg_dish":
                warnings.append("⚠️ Яйца — основа этого блюда. Замена изменит его характер — предлагаем альтернативные рецепты.")
                alternative_dishes = cls.ALTERNATIVE_DISHES.get("egg_dish",[])
            if ing_name == "яйца" and egg_role == "garnish" and planned_sub in ["банан","банан (пюре)"]:
                impossible_reasons.append("❌ Банан нельзя использовать вместо яиц в несладком салате")
        if len(issues) > 3:
            warnings.append(f"⚠️ Требуется заменить {len(issues)} ингредиентов — итоговое блюдо может существенно отличаться от оригинала.")
        if any(i.get("name","") == "яйца" or i.get("ingredient","") == "яйца" for i in issues):
            if egg_role in cls.ALTERNATIVE_DISHES and not alternative_dishes:
                alternative_dishes = cls.ALTERNATIVE_DISHES[egg_role]
        if impossible_reasons:
            level, feasible = "impossible", False
        elif len(issues) == 0:
            level, feasible = "easy", True
        elif len(issues) <= 2:
            level, feasible = "medium", True
        elif len(issues) <= 4:
            level, feasible = "hard", True
        else:
            level, feasible = "hard", True
            warnings.append("⚠️ Много замен — рекомендуем рассмотреть альтернативные блюда.")
        return {"feasible":feasible,"level":level,"warnings":warnings,"impossible_reasons":impossible_reasons,"alternative_dishes":alternative_dishes}


class DietAnalyzer:
    def __init__(self):
        self.diet_restrictions = {
            "Кето":{"запрещено":["сахар","мука","крупы","хлеб","макароны","морковь","картофель","рис","банан","виноград","мед","конфеты","фасоль","чечевица","горох","горошек","нут","бобы","кукуруза","манка","овсянка","гречка"],"разрешено":["мясо","рыба","яйца","сыр","орехи","авокадо","масло растительное","масло сливочное","сливки","миндальная мука","кокосовая мука","стевия","эритрит","грибы","цветная капуста","брокколи","тофу","кабачок","нутовая мука"]},
            "Веган":{"запрещено":["молоко","яйца","масло сливочное","творог","сыр","кефир","йогурт","сметана","сливки","мед","желатин","курица","говядина","рыба","мясо","морепродукты","майонез","колбаса","сосиски","ветчина","бекон"],"разрешено":["овощи","фрукты","орехи","бобовые","масло растительное","тофу","нутовая мука","льняная мука","аквафаба"]},
            "Вегетарианец":{"запрещено":["мясо","рыба","курица","говядина","свинина","морепродукты","колбаса","сосиски","ветчина","бекон"],"разрешено":["молоко","яйца","сыр","творог","овощи","фрукты","орехи","тофу","бобовые"]},
            "Без сахара":{"запрещено":["сахар","мед","кленовый сироп","патока","конфеты","шоколад","варенье","джем"],"разрешено":["стевия","эритрит"]},
            "без глютена":{"запрещено":["мука","манка","булгур","соевый соус","пшеница","овсянка"],"разрешено":["рисовая мука","кукурузная мука","гречневая мука","миндальная мука","нутовая мука"]},
            "лактоза":{"запрещено":["молоко","сливки","сметана","йогурт","творог","сыр","кефир","масло сливочное","мороженое"],"разрешено":["растительное молоко","кокосовое молоко","тофу","масло растительное"]},
        }
        self._subs_cache = None

    def _load_substitutions(self):
        if self._subs_cache is not None:
            return self._subs_cache
        try:
            f = "data/substitutions.json"
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fp:
                    self._subs_cache = json.load(fp).get("substitutions",[])
                    return self._subs_cache
        except Exception:
            pass
        return []

    def check_compatibility(self, ingredient, diet, dish_context=None):
        if not diet or diet == "Нет":
            return True, None, None
        name = ingredient.get("name","").lower().strip()
        for prefix in ["консервированный ","консервированная ","консервированное "]:
            name = name.replace(prefix,"")
        if diet in self.diet_restrictions:
            for forbidden in self.diet_restrictions[diet].get("запрещено",[]):
                if forbidden.lower() in name or name in forbidden.lower():
                    alts = self.find_alternatives(name, diet, dish_context=dish_context)
                    return False, f"Запрещено на диете {diet}", alts
        return True, None, None

    def find_alternatives(self, ingredient_name, diet=None, dish_context=None):
        subs = self._load_substitutions()
        alternatives = []
        egg_role = (dish_context or {}).get("egg_role","general")
        is_sweet = (dish_context or {}).get("is_sweet",False)
        for sub in subs:
            ing = sub.get("ingredient","")
            if not (ing == ingredient_name or ingredient_name in ing or ing in ingredient_name):
                continue
            condition = sub.get("condition","")
            sub_role = sub.get("dish_role")
            diet_match = (diet and condition.lower() == diet.lower()) or condition in ["всегда","любая"]
            if not diet_match:
                continue
            if sub_role and sub_role != egg_role and sub_role != "general":
                continue
            alt_name = sub["alternative"]
            skip = False
            if "банан" in alt_name and not is_sweet:
                skip = True
            if "аквафаба" in alt_name and egg_role == "garnish":
                skip = True
            if egg_role == "leavening" and any(x in alt_name for x in ["тофу","нут отварной","авокадо"]):
                skip = True
            if skip:
                continue
            if not any(a["name"] == alt_name for a in alternatives):
                alternatives.append({"name":alt_name,"description":sub.get("note",f"Замена: {alt_name}"),"type":"прямая замена","ratio":sub.get("ratio",1.0),"dish_role":sub_role})
        return alternatives

    def get_diet_info(self, diet):
        return self.diet_restrictions.get(diet,{})

    def analyze_recipe_for_diet(self, ingredients, diet, recipe_name="", category=""):
        issues, alternatives_suggested = [], []
        dish_context = DishContextClassifier.classify(recipe_name, category)
        for ing in ingredients:
            compatible, reason, alts = self.check_compatibility(ing, diet, dish_context=dish_context)
            if not compatible:
                issues.append({"ingredient":ing["name"],"reason":reason,"alternatives":(alts or [])[:3],"dish_context":dish_context})
                if alts:
                    alternatives_suggested.append({"original":ing["name"],"suggested":alts[0]["name"],"note":alts[0]["description"]})
        return {"is_compatible":len(issues)==0,"issues":issues,"suggestions":alternatives_suggested,"diet_name":diet,"dish_context":dish_context}


def analyze_diet_compatibility(ingredient, diet, dish_context=None):
    analyzer = DietAnalyzer()
    compatible, reason, alternatives = analyzer.check_compatibility(ingredient, diet, dish_context=dish_context)
    if not compatible and alternatives:
        alt_text = " | ".join([f"{a['name']} ({a['description']})" for a in alternatives[:2]])
        return False, alt_text
    return compatible, None

diet_analyzer = DietAnalyzer()