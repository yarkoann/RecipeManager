"""
app.py — точка входа приложения RecipeManager.
Запуск: streamlit run app.py
"""
import json
import streamlit as st
from datetime import datetime

from components.recipe_adapter import RecipeAdapter
from components.diet_analyzer import DishContextClassifier
from components.ui_helpers import load_css, parse_ingredients_text, show_result

# ── Инициализация ──────────────────────────────────────────────────────────────
adapter = RecipeAdapter()

st.set_page_config(page_title="Умный адаптер рецептов", page_icon="🍳", layout="wide")
load_css()

st.markdown('<h1 class="main-header">Умный адаптер рецептов</h1>', unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [
    ("adaptation_history", []),
    ("edit_recipe_id", None),
    ("delete_confirm_id", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Боковая панель ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Навигация")
    with st.expander("Как это работает", expanded=False):
        st.markdown("""
        1. **Выберите рецепт** из базы
        2. **Укажите продукты**, которые есть
        3. **Добавьте аллергии** и диету
        4. **Получите адаптированный рецепт** с заменами и КБЖУ!

        **Совет:** Оставив поле продуктов пустым — считается, что всё есть.
        Если продукта нет совсем — указать `0` (например: `яйца 0 шт`).
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
                            {"name": "какао", "quantity": 50, "unit": "г"},
                        ],
                        "steps": ["Смешать сухие ингредиенты", "Добавить яйца и молоко", "Выпекать 30 мин при 180°C"],
                        "time": 60, "difficulty": "средняя",
                    },
                    {
                        "id": 2, "name": "Блины", "category": "завтраки",
                        "ingredients": [
                            {"name": "мука", "quantity": 200, "unit": "г"},
                            {"name": "молоко", "quantity": 500, "unit": "мл"},
                            {"name": "яйца", "quantity": 2, "unit": "шт"},
                            {"name": "сахар", "quantity": 20, "unit": "г"},
                            {"name": "масло растительное", "quantity": 30, "unit": "мл"},
                            {"name": "соль", "quantity": 2, "unit": "г"},
                        ],
                        "steps": ["Смешать все ингредиенты", "Жарить на сковороде"],
                        "time": 30, "difficulty": "легкая",
                    },
                    {
                        "id": 3, "name": "Сырники", "category": "завтраки",
                        "ingredients": [
                            {"name": "творог", "quantity": 500, "unit": "г"},
                            {"name": "яйца", "quantity": 1, "unit": "шт"},
                            {"name": "мука", "quantity": 100, "unit": "г"},
                            {"name": "сахар", "quantity": 50, "unit": "г"},
                            {"name": "соль", "quantity": 1, "unit": "г"},
                        ],
                        "steps": ["Смешать творог с яйцом", "Добавить муку и сахар", "Обжарить на сковороде"],
                        "time": 40, "difficulty": "легкая",
                    },
                    {
                        "id": 4, "name": "Салат \"Оливье\"", "category": "салаты",
                        "ingredients": [
                            {"name": "картофель", "quantity": 400.0, "unit": "г"},
                            {"name": "яйца", "quantity": 6.0, "unit": "шт"},
                            {"name": "огурцы соленые", "quantity": 300.0, "unit": "г"},
                            {"name": "колбаса", "quantity": 300.0, "unit": "г"},
                            {"name": "майонез", "quantity": 300.0, "unit": "мл"},
                            {"name": "горох", "quantity": 1.0, "unit": "банка"},
                        ],
                        "steps": [
                            "Отварить яйца и картофель",
                            "Нарезать кубиком картофель, яйца, огурцы и колбасу",
                            "Смешать все ингредиенты в миске, заправить майонезом",
                        ],
                        "time": 30, "difficulty": "легкая",
                    },
                    {
                        "id": 5, "name": "Омлет с помидором", "category": "завтраки",
                        "ingredients": [
                            {"name": "яйца", "quantity": 2.0, "unit": "шт", "by_taste": False},
                            {"name": "помидор", "quantity": 1.0, "unit": "шт", "by_taste": False},
                            {"name": "соль", "quantity": None, "unit": "", "by_taste": True},
                            {"name": "майонез", "quantity": None, "unit": "", "by_taste": True},
                        ],
                        "steps": ["Промыть и нарезать помидор", "Взбить яйца с солью", "Жарить яйца вместе с помидором до готовности"],
                        "time": 5, "difficulty": "легкая", "servings": 1,
                    },
                ],
            }
            with open("data/recipes.json", "w", encoding="utf-8") as f:
                json.dump(default_recipes, f, ensure_ascii=False, indent=2)
            st.success("Базовые рецепты восстановлены!")
            st.rerun()

    if st.session_state.adaptation_history:
        with st.expander(f"История адаптаций ({len(st.session_state.adaptation_history)})", expanded=False):
            for h in reversed(st.session_state.adaptation_history[-10:]):
                st.caption(f"**{h['recipe']}** — {h['time']}")
                if h.get("diet") and h["diet"] != "Нет":
                    st.caption(f"Диета: {h['diet']}")
            if st.button("Очистить историю"):
                st.session_state.adaptation_history = []
                st.rerun()


# ── Вкладки ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Выбрать из базы",
    "Поиск по продуктам",
    "Управление рецептами",
    "Добавить рецепт",
])


# ═══════════════════════════════════════════════════════════════════════════════
#  Вкладка 1: Выбор рецепта из базы
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Выбери рецепт из базы")
    col1, col2 = st.columns([1, 1])

    with col1:
        search_query = st.text_input("Поиск по названию", key="search_tab1")
        all_recipes = adapter.manager.get_all_recipes()

        if search_query:
            filtered_recipes = [r for r in all_recipes if search_query.lower() in r["name"].lower()]
        else:
            categories = sorted(set(r.get("category", "другие") for r in all_recipes))
            selected_category = st.selectbox("Категория", ["Все"] + categories, key="cat_tab1")
            filtered_recipes = (
                all_recipes if selected_category == "Все"
                else [r for r in all_recipes if r.get("category") == selected_category]
            )

    with col2:
        if filtered_recipes:
            recipe_names = [r["name"] for r in filtered_recipes]
            selected_name = st.selectbox("Выбери рецепт", recipe_names, key="recipe_tab1")
            selected_recipe = next(r for r in filtered_recipes if r["name"] == selected_name)

            ctx = DishContextClassifier.classify(
                selected_recipe.get("name", ""), selected_recipe.get("category", "")
            )
            dish_type_label = []
            if ctx["is_sweet"]:
                dish_type_label.append("Выпечка/Десерт")
            if ctx["is_savory"]:
                dish_type_label.append("Несладкое блюдо")
            if dish_type_label:
                st.caption("Тип блюда: " + " | ".join(dish_type_label))

            time_val = selected_recipe.get("time")
            diff_val = selected_recipe.get("difficulty", "")
            if time_val or diff_val:
                st.caption(f"⏱ {time_val} мин  •  Сложность: {diff_val}")

            st.markdown("**Ингредиенты:**")
            for ing in selected_recipe["ingredients"]:
                if ing.get("by_taste", False):
                    st.markdown(f"• {ing['name']} (по вкусу)")
                elif ing.get("unit") == "банка":
                    from components.recipe_manager import can_to_grams as _ctg
                    grams = _ctg(ing["name"], ing["quantity"])
                    st.markdown(f"• {ing['name']}: {ing['quantity']} банка (≈{int(grams)} г)")
                else:
                    st.markdown(f"• {ing['name']}: {ing['quantity']} {ing['unit']}")
        else:
            st.warning("Рецепты не найдены")

    if filtered_recipes and "selected_recipe" in locals():
        st.markdown("---")
        st.subheader("Какие продукты у тебя есть?")
        user_products = st.text_area(
            "Введи продукты через запятую",
            placeholder="мука 500г, яйца 3 шт, молоко 200мл, горох 1 банка, разрыхлитель 0г",
            key="products_tab1", height=80,
            help="Формат: продукт количество единица\nОставь пустым — считается, что всё есть\nЕсли продукта нет — укажи 0",
        )
        col1, col2 = st.columns(2)
        with col1:
            allergies_input = st.text_input(
                "Аллергии (через запятую)", placeholder="лактоза, глютен, яйца", key="allergy_tab1"
            )
        with col2:
            diet = st.selectbox("Диета", ["Нет", "Веган", "Вегетарианец", "Без сахара", "Кето"], key="diet_tab1")

        if st.button("Адаптировать", type="primary", use_container_width=True, key="adapt_tab1"):
            allergies = (
                [a.strip().lower() for a in allergies_input.split(",") if a.strip()]
                if allergies_input else []
            )
            with st.spinner("ИИ анализирует рецепт..."):
                result = adapter.adapt_recipe(selected_recipe, user_products or "", allergies, diet)
            st.session_state.adaptation_history.append({
                "recipe": result["recipe_name"],
                "diet": diet,
                "time": datetime.now().strftime("%H:%M"),
            })
            st.markdown("---")
            show_result(result)


# ═══════════════════════════════════════════════════════════════════════════════
#  Вкладка 2: Поиск по продуктам
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Что приготовить из того, что есть?")
    st.write("Введи продукты — система найдёт подходящие рецепты и покажет, чего не хватает.")

    products_input = st.text_area(
        "Твои продукты",
        placeholder="мука, яйца, молоко, картофель, лук, масло растительное",
        height=80, key="products_tab2",
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        min_match_pct = st.slider("Минимальный % совпадения ингредиентов", 0, 100, 30, 10)
    with col2:
        show_top = st.selectbox("Показать топ", [5, 10, 15, 20], index=0)

    if st.button("Найти рецепты", type="primary", key="search_products"):
        if products_input.strip():
            user_products_list = adapter.parse_user_products(products_input)
            results = adapter.manager.search_by_available_ingredients(user_products_list)
            filtered = [r for r in results if r["pct"] >= min_match_pct][:show_top]

            if filtered:
                st.success(f"Найдено {len(filtered)} рецептов (из {len(results)} в базе)")
                for res in filtered:
                    recipe = res["recipe"]
                    pct = res["pct"]
                    color = "🟢" if pct >= 80 else "🟡" if pct >= 50 else "🔴"

                    with st.expander(f"{color} **{recipe['name']}** — {pct}% ингредиентов есть"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Есть", f"{res['matched']}/{res['total']}")
                        c2.metric("Не хватает", res["missing"])
                        c3.metric("Совпадение", f"{pct}%")

                        user_names = {p["name"].lower() for p in user_products_list}
                        have, need = [], []
                        for ing in recipe.get("ingredients", []):
                            if ing.get("by_taste") or ing.get("quantity") is None:
                                continue
                            if any(u in ing["name"].lower() or ing["name"].lower() in u for u in user_names):
                                have.append(ing["name"])
                            else:
                                need.append(ing["name"])

                        col_h, col_n = st.columns(2)
                        with col_h:
                            if have:
                                st.markdown("**✅ Есть:**")
                                for h in have:
                                    st.markdown(f"• {h}")
                        with col_n:
                            if need:
                                st.markdown("**Докупить:**")
                                for n in need:
                                    st.markdown(f"• {n}")

                        if st.button(f"Адаптировать этот рецепт", key=f"adapt_search_{recipe.get('id', 0)}"):
                            with st.spinner("ИИ анализирует..."):
                                result = adapter.adapt_recipe(recipe, products_input, [], "Нет")
                            st.session_state.adaptation_history.append({
                                "recipe": result["recipe_name"], "diet": "Нет",
                                "time": datetime.now().strftime("%H:%M"),
                            })
                            show_result(result)
            else:
                st.warning(f"Нет рецептов с совпадением ≥ {min_match_pct}%. Попробуй снизить порог.")
        else:
            st.error("Введи хотя бы один продукт!")


# ═══════════════════════════════════════════════════════════════════════════════
#  Вкладка 3: Управление рецептами
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Управление рецептами")
    all_recipes_manage = adapter.manager.get_all_recipes()

    if not all_recipes_manage:
        st.info("База рецептов пуста.")
    else:
        recipe_options = {r["name"]: r for r in all_recipes_manage}
        selected_manage_name = st.selectbox("Выбери рецепт", list(recipe_options.keys()), key="manage_select")
        managing_recipe = recipe_options[selected_manage_name]

        col_edit, col_del, col_dup = st.columns(3)
        with col_edit:
            if st.button("Редактировать", use_container_width=True):
                st.session_state.edit_recipe_id = managing_recipe.get("id")
                st.session_state.delete_confirm_id = None
        with col_del:
            if st.button("Удалить", use_container_width=True, type="secondary"):
                st.session_state.delete_confirm_id = managing_recipe.get("id")
                st.session_state.edit_recipe_id = None
        with col_dup:
            if st.button("Дублировать", use_container_width=True):
                new_recipe = managing_recipe.copy()
                new_recipe["name"] = managing_recipe["name"] + " (копия)"
                new_recipe.pop("id", None)
                nid = adapter.manager.add_recipe(new_recipe)
                if nid:
                    st.success(f"Рецепт скопирован с ID {nid}!")
                    st.rerun()
                else:
                    st.error("Такое имя уже существует!")

        st.markdown("---")

        # Подтверждение удаления
        if st.session_state.delete_confirm_id == managing_recipe.get("id"):
            st.error(f"⚠️ Удалить рецепт **\"{managing_recipe['name']}\"**? Это действие необратимо.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Да, удалить", type="primary", use_container_width=True):
                    if adapter.manager.delete_recipe(managing_recipe["id"]):
                        st.success("Рецепт удалён!")
                        st.session_state.delete_confirm_id = None
                        st.rerun()
                    else:
                        st.error("Ошибка при удалении")
            with c2:
                if st.button("Отмена", use_container_width=True):
                    st.session_state.delete_confirm_id = None
                    st.rerun()

        # Форма редактирования
        elif st.session_state.edit_recipe_id == managing_recipe.get("id"):
            st.subheader(f"Редактирование: {managing_recipe['name']}")
            with st.form(f"edit_form_{managing_recipe['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Название", value=managing_recipe["name"])
                with col2:
                    new_servings = st.number_input("Порций", min_value=1, value=managing_recipe.get("servings", 2))

                CATEGORIES = ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"]
                cur_cat = managing_recipe.get("category", "другие")
                new_category = st.selectbox(
                    "Категория", CATEGORIES,
                    index=CATEGORIES.index(cur_cat) if cur_cat in CATEGORIES else 0,
                )

                existing_ing_lines = []
                for ing in managing_recipe.get("ingredients", []):
                    if ing.get("by_taste") or ing.get("quantity") is None:
                        existing_ing_lines.append(f"{ing['name']} по вкусу")
                    elif ing.get("unit") == "банка":
                        existing_ing_lines.append(f"{ing['name']} {ing['quantity']} банка")
                    else:
                        existing_ing_lines.append(f"{ing['name']} {ing['quantity']}{ing.get('unit', 'г')}")

                new_ingredients_text = st.text_area(
                    "Ингредиенты (каждый с новой строки)",
                    value="\n".join(existing_ing_lines), height=180,
                )
                new_steps_text = st.text_area(
                    "Шаги приготовления (каждый с новой строки)",
                    value="\n".join(managing_recipe.get("steps", [])), height=150,
                )

                col_t, col_d = st.columns(2)
                with col_t:
                    new_time = st.number_input("Время (мин)", min_value=1, value=managing_recipe.get("time", 30))
                with col_d:
                    diff_opts = ["легкая", "средняя", "сложная"]
                    cur_diff = managing_recipe.get("difficulty", "средняя")
                    new_difficulty = st.selectbox(
                        "Сложность", diff_opts,
                        index=diff_opts.index(cur_diff) if cur_diff in diff_opts else 1,
                    )

                save_col, cancel_col = st.columns(2)
                with save_col:
                    save_btn = st.form_submit_button("Сохранить", type="primary", use_container_width=True)
                with cancel_col:
                    cancel_btn = st.form_submit_button("Отмена", use_container_width=True)

                if save_btn:
                    new_ingredients, invalid = parse_ingredients_text(new_ingredients_text, adapter)
                    if invalid:
                        st.warning(f"Не удалось распознать: {', '.join(invalid)}")
                    if new_name and new_ingredients:
                        new_steps = [s.strip() for s in new_steps_text.strip().split("\n") if s.strip()]
                        updated = {
                            "name": new_name, "category": new_category,
                            "ingredients": new_ingredients, "steps": new_steps,
                            "time": new_time, "difficulty": new_difficulty, "servings": new_servings,
                        }
                        if adapter.manager.update_recipe(managing_recipe["id"], updated):
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

        # Превью рецепта
        else:
            st.markdown(
                f"**Категория:** {managing_recipe.get('category', '—')} "
                f"• **Время:** {managing_recipe.get('time', '?')} мин "
                f"• **Сложность:** {managing_recipe.get('difficulty', '?')}"
            )
            st.markdown("**Ингредиенты:**")
            for ing in managing_recipe.get("ingredients", []):
                if ing.get("by_taste"):
                    st.markdown(f"• {ing['name']} — по вкусу")
                elif ing.get("unit") == "банка":
                    st.markdown(f"• {ing['name']} — {ing['quantity']} банка")
                else:
                    st.markdown(f"• {ing['name']} — {ing.get('quantity', '?')} {ing.get('unit', '')}")
            if managing_recipe.get("steps"):
                with st.expander("Шаги приготовления"):
                    for i, step in enumerate(managing_recipe["steps"], 1):
                        st.write(f"{i}. {step}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Вкладка 4: Добавить рецепт
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Добавить новый рецепт")

    with st.form("add_recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("Название рецепта")
        with col2:
            servings_manual = st.number_input("Количество порций", min_value=1, value=2)

        CATEGORIES = ["завтраки", "супы", "основные", "десерты", "салаты", "выпечка", "соусы", "другие"]
        category = st.selectbox("Категория", CATEGORIES)

        if recipe_name:
            ctx_preview = DishContextClassifier.classify(recipe_name, category)
            if ctx_preview["is_sweet"]:
                st.caption("🍰 Определён как выпечка/десерт — замены яиц будут для выпечки")
            elif ctx_preview["is_savory"]:
                st.caption("🥗 Определён как несладкое блюдо — замены яиц будут для горячего/салатов")

        ingredients_text = st.text_area(
            "Ингредиенты (каждый с новой строки)",
            placeholder="мука 200г\nяйца 2 шт\nмолоко 100мл\nсоль по вкусу\nгорох 1 банка",
            height=150,
            help="Формат: название количество единица. Банки: 'горох 1 банка'",
        )
        steps_text = st.text_area(
            "Шаги приготовления (каждый с новой строки)",
            placeholder="Смешать сухие ингредиенты\nДобавить яйца и молоко\nВыпекать 30 мин",
            height=150,
        )
        col1, col2 = st.columns(2)
        with col1:
            time_val = st.number_input("Время приготовления (мин)", min_value=5, value=30)
        with col2:
            difficulty = st.selectbox("Сложность", ["легкая", "средняя", "сложная"])

        submitted = st.form_submit_button("Сохранить рецепт", type="primary", use_container_width=True)

        if submitted:
            if recipe_name and ingredients_text:
                existing_names = [r["name"].lower() for r in adapter.manager.get_all_recipes()]
                if recipe_name.lower() in existing_names:
                    st.error(f"Рецепт '{recipe_name}' уже существует!")
                else:
                    ingredients, invalid_lines = parse_ingredients_text(ingredients_text, adapter)
                    if invalid_lines:
                        st.warning(f"Не удалось распознать: {', '.join(invalid_lines)}")
                    steps = [s.strip() for s in steps_text.strip().split("\n") if s.strip()]
                    if ingredients:
                        new_recipe = {
                            "name": recipe_name, "category": category,
                            "ingredients": ingredients, "steps": steps,
                            "time": time_val, "difficulty": difficulty, "servings": servings_manual,
                        }
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
st.markdown("<center>Умный адаптер рецептов — курсовая работа по ИИ</center>", unsafe_allow_html=True)
