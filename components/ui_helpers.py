"""
ui_helpers.py — вспомогательные функции для интерфейса Streamlit:
    * парсинг ингредиентов из текста
    * отображение результата адаптации
    * загрузка CSS
"""
import os
import re
import streamlit as st

from components.recipe_manager import can_to_grams
from components.diet_analyzer import DishContextClassifier
from components.nutrition import calculate_nutrition


# ── CSS ───────────────────────────────────────────────────────────────────────

def load_css():
    css_file = "static/css/style.css"
    if os.path.exists(css_file):
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── Парсинг ингредиентов ──────────────────────────────────────────────────────

def parse_ingredients_text(text: str, adapter) -> tuple:
    """Парсит текст ингредиентов, возвращает (список, ошибки)."""
    ingredients = []
    invalid_lines = []
    taste_phrases = ["по вкусу", "по желанию", "опционально", "по необходимости"]
    for line in text.strip().split("\n"):
        line = line.strip().replace(",", "")
        if not line:
            continue
        is_by_taste = any(p in line.lower() for p in taste_phrases)
        match = re.search(
            r"([а-яА-Я\s]+?)\s+(\d+[.,]?\d*)\s*(банка|банки|банок|б|г|мл|шт|ст\.л|ч\.л|кг|л)?",
            line,
        )
        if match:
            name = adapter.normalize_ingredient_name(match.group(1).strip().lower())
            qty = float(match.group(2).replace(",", "."))
            unit = match.group(3) or "шт"
            if unit in ["банка", "банки", "банок", "б"]:
                unit = "банка"
            ingredients.append({"name": name, "quantity": qty, "unit": unit, "by_taste": False})
        elif is_by_taste:
            clean = line.lower()
            for p in taste_phrases:
                clean = clean.replace(p, "").strip()
            name = adapter.normalize_ingredient_name(clean or line.lower())
            ingredients.append({"name": name, "quantity": None, "unit": "", "by_taste": True})
        else:
            invalid_lines.append(line)
    return ingredients, invalid_lines


# ── Функция для генерации текста для копирования (с КБЖУ, без эмодзи) ─────────

def generate_copy_text(result: dict, nutrition: dict) -> str:
    """
    Генерирует текст рецепта для копирования в буфер обмена.
    Включает КБЖУ и всю полезную информацию.
    """
    lines = [
        f"Рецепт: {result['recipe_name']}",
        "-" * 50,
        f"Порций: ~{result['servings']}",
        "",
        "ИНГРЕДИЕНТЫ:",
        "-" * 30,
    ]

    # Ингредиенты
    for ing in result["ingredients"]:
        if ing.get("by_taste"):
            lines.append(f"  * {ing['name']} — по вкусу")
        elif ing.get("unit") == "банка":
            grams = can_to_grams(ing.get("name", ""), ing["quantity"])
            lines.append(f"  * {ing['name']} — {ing['quantity']} банка (~{int(grams)} г)")
        else:
            unit_display = ing.get('unit', '')
            if unit_display == "ст.л":
                unit_display = "ст.л."
            elif unit_display == "ч.л":
                unit_display = "ч.л."
            lines.append(f"  * {ing['name']} — {ing.get('quantity', '?')} {unit_display}")

    # Замены (если есть)
    if result["substitutions"]:
        lines.extend([
            "",
            "ПРОИЗВЕДЁННЫЕ ЗАМЕНЫ:",
            "-" * 30,
        ])
        for sub in result["substitutions"]:
            lines.append(f"  * {sub['original']} -> {sub['alternative']}")

    # Шаги приготовления
    if result["steps"]:
        lines.extend([
            "",
            "ПРИГОТОВЛЕНИЕ:",
            "-" * 30,
        ])
        for i, step in enumerate(result["steps"], 1):
            lines.append(f"  {i}. {step}")

    # Предупреждения (если есть)
    feas = result.get("feasibility", {})
    if feas.get("warnings"):
        lines.extend([
            "",
            "ПРЕДУПРЕЖДЕНИЯ:",
            "-" * 30,
        ])
        for w in feas["warnings"]:
            lines.append(f"  * {w}")

    # КБЖУ (пищевая ценность)
    if nutrition and nutrition.get("ккал", 0) > 0:
        lines.extend([
            "",
            "ПИЩЕВАЯ ЦЕННОСТЬ (на всё блюдо):",
            "-" * 30,
            f"  Калории: {int(nutrition['ккал'])} ккал",
            f"  Белки: {nutrition['белки']} г",
            f"  Жиры: {nutrition['жиры']} г",
            f"  Углеводы: {nutrition['углеводы']} г",
        ])

        # На порцию
        if result["servings"] > 1:
            lines.extend([
                "",
                f"НА 1 ПОРЦИЮ (всего {result['servings']} порций):",
                f"  Калории: {int(nutrition['ккал'] / result['servings'])} ккал",
                f"  Белки: {round(nutrition['белки'] / result['servings'], 1)} г",
                f"  Жиры: {round(nutrition['жиры'] / result['servings'], 1)} г",
                f"  Углеводы: {round(nutrition['углеводы'] / result['servings'], 1)} г",
            ])

    lines.extend([
        "",
        "-" * 50,
        "Адаптировал Умный адаптер рецептов",
    ])

    return "\n".join(lines)


# ── Отображение результата ────────────────────────────────────────────────────

def show_result(result: dict):
    """Отображает полный результат адаптации рецепта."""
    st.markdown(f"## {result['recipe_name']}")

    # Контекст блюда
    dctx = result.get("dish_context", {})
    if dctx.get("egg_role") and dctx["egg_role"] != "general":
        label = DishContextClassifier.egg_role_label(dctx["egg_role"])
        if label:
            st.info(label)

    # Оценка возможности адаптации
    feas = result.get("feasibility", {})
    if feas.get("impossible_reasons"):
        st.error("**Адаптация частично невозможна:**")
        for reason in feas["impossible_reasons"]:
            st.error(reason)
        if feas.get("alternative_dishes"):
            st.markdown("### Рекомендуемые альтернативные блюда:")
            for alt in feas["alternative_dishes"]:
                st.success(f"**{alt['name']}** — {alt['note']}")
    elif feas.get("warnings"):
        for w in feas["warnings"]:
            st.warning(w)
        if feas.get("alternative_dishes"):
            with st.expander("Альтернативные блюда без проблемных ингредиентов"):
                for alt in feas["alternative_dishes"]:
                    st.write(f"• **{alt['name']}** — {alt['note']}")

    st.markdown(f"### Примерно на **{result['servings']}** персон")

    if result["scale_factor"] != 1.0:
        if result["scale_factor"] < 1.0:
            st.info(f"**Рецепт уменьшен на {int((1 - result['scale_factor']) * 100)}%**")
        else:
            st.info(f"**Рецепт увеличен в {result['scale_factor']:.1f} раз**")

    # Избыток / нехватка / аллергены / диета
    if result["excess"]:
        with st.expander("Избыток продуктов"):
            for e in result["excess"]:
                st.write(
                    f"• {e['name']}: нужно {e['recipe_needs']}{e['unit']}, "
                    f"у вас {e['user_has']}{e['unit']} (останется {e['excess']}{e['unit']})"
                )
    if result["short"]:
        with st.expander("Продуктов меньше нормы"):
            for s in result["short"]:
                st.write(
                    f"• {s['name']}: нужно {s['quantity']}{s['unit']}, "
                    f"есть {s['user_quantity']}{s['unit']}"
                )
            st.info("Если продукта нет совсем — укажи его с 0")

    if result["allergy_issues"]:
        with st.expander("Аллергены"):
            for a in result["allergy_issues"]:
                st.write(f"• {a['name']} содержит аллерген: {a['allergen']}")
    if result["diet_issues"]:
        with st.expander("Проблемы с диетой"):
            for d in result["diet_issues"]:
                st.write(f"• {d['name']} не соответствует диете {d['diet']}")

    # Замены
    if result["substitutions"]:
        with st.expander("Произведённые замены"):
            for sub in result["substitutions"]:
                st.write(f"• **{sub['original']}** → **{sub['alternative']}**")
                st.caption(f"  Причина: {sub['reason']}")
                if sub["note"]:
                    st.caption(f"ⓘ: {sub['note']}")

    # Альтернативные замены
    if result.get("alternatives"):
        with st.expander("Другие доступные альтернативы"):
            for alt_group in result["alternatives"]:
                if len(alt_group["alternatives"]) > 1:
                    st.markdown(f"**{alt_group['original']}** → можно заменить на:")
                    for alt in alt_group["alternatives"]:
                        is_selected = any(
                            s["original"] == alt_group["original"] and s["alternative"] == alt["name"]
                            for s in result["substitutions"]
                        )
                        if not is_selected:
                            pct = int(alt["confidence"] * 100)
                            st.markdown(f"  • **{alt['name']}** (уверенность ИИ: {pct}%)")
                            if alt["note"]:
                                st.caption(f"ⓘ: {alt['note']}")
                    st.markdown("---")

    # Список ингредиентов после адаптации
    st.markdown("### Ингредиенты после адаптации:")
    for ing in result["ingredients"]:
        c1, c2, c3 = st.columns([3, 1, 2])
        with c1:
            if ing.get("is_substitute"):
                st.markdown(f"**{ing['name']}** 🔄")
            elif ing.get("limited"):
                st.markdown(f"**{ing['name']}** ⚠️")
            else:
                st.markdown(f"**{ing['name']}**")
        with c2:
            if ing.get("by_taste"):
                st.markdown("по вкусу")
            elif ing.get("unit") == "банка":
                grams = can_to_grams(ing.get("name", ""), ing["quantity"])
                st.markdown(f"{ing['quantity']} банка (~{int(grams)}г)")
            else:
                st.markdown(f"{ing.get('quantity', '?')}{ing.get('unit', '')}")
        with c3:
            if ing.get("original_name"):
                st.caption(f"замена {ing['original_name']}")
            elif ing.get("limited"):
                st.caption(f"нужно {ing['original_quantity']}{ing.get('unit', '')}")

    # КБЖУ
    nutrition = calculate_nutrition(result["ingredients"])
    if nutrition["ккал"] > 0:
        st.markdown("### Примерная пищевая ценность (на всё блюдо):")
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Калории", f"{int(nutrition['ккал'])} ккал")
        n2.metric("Белки", f"{nutrition['белки']} г")
        n3.metric("Жиры", f"{nutrition['жиры']} г")
        n4.metric("Углеводы", f"{nutrition['углеводы']} г")
        if result["servings"] > 1:
            st.caption(
                f"На 1 порцию: {int(nutrition['ккал'] / result['servings'])} ккал / "
                f"Б: {round(nutrition['белки'] / result['servings'], 1)}г / "
                f"Ж: {round(nutrition['жиры'] / result['servings'], 1)}г / "
                f"У: {round(nutrition['углеводы'] / result['servings'], 1)}г"
            )

    # Шаги приготовления
    if result["steps"]:
        with st.expander("Шаги приготовления"):
            for i, step in enumerate(result["steps"], 1):
                st.write(f"{i}. {step}")

    # Скопировать рецепт в буфер обмена
    with st.expander("Скопировать рецепт в буфер обмена"):
        copy_text = generate_copy_text(result, nutrition)
        safe_text = copy_text.replace('`', '\\`').replace('${', '\\${')


        # Поле с рецептом
        st.code(copy_text, language="markdown", line_numbers=False)

        # для копирования по клику
        st.markdown(f'''
        <script>
        (function() {{
            const codeBlock = window.parent.document.querySelector('.stCode pre');
            if (codeBlock) {{
                codeBlock.style.cursor = 'pointer';
                codeBlock.addEventListener('click', function() {{
                    navigator.clipboard.writeText(`{safe_text}`).then(function() {{
                        const msg = window.parent.document.getElementById('copyMsg');
                        if (msg) {{
                            msg.style.display = 'block';
                            setTimeout(function() {{ msg.style.display = 'none'; }}, 2000);
                        }}
                    }});
                }});
            }}
        }})();
        </script>
        ''', unsafe_allow_html=True)
