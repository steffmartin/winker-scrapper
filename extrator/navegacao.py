"""Operações de navegação nos elementos do portal Winker."""

import time


def set_ion_datetime(iframe, selector_index, target_month, target_year):
    """
    Interage com o componente ion-datetime selecionando mês e ano.
    """
    datetime_elements = iframe.locator("ion-datetime").all()
    if len(datetime_elements) <= selector_index:
        return False

    datetime_elements[selector_index].click()
    iframe.locator("ion-picker-cmp").wait_for(state="visible", timeout=10000)

    def navigate_sequentially(col_class, target_value, is_month):
        column = iframe.locator(f"ion-picker-cmp .{col_class}")
        if not column.is_visible():
            return False

        selected_locator = column.locator("button.picker-opt-selected")
        if not selected_locator.is_visible():
            column.get_by_role("button", name=target_value, exact=True).click()
            return

        current_val_text = selected_locator.inner_text().strip()
        current_val = int(current_val_text)
        target_val = int(target_value)

        if current_val == target_val:
            return

        step = -1 if target_val < current_val else 1
        for val in range(current_val + step, target_val + step, step):
            val_str = str(val).zfill(2) if is_month else str(val)
            column.get_by_role("button", name=val_str, exact=True).click()
            time.sleep(0.1) # Mantido: Navegação entre números

    try:
        navigate_sequentially("picker-opts-right", target_month, True)
        navigate_sequentially("picker-opts-left", target_year, False)
        iframe.get_by_role("button", name="Confirmar").click()
        
        # Aguarda o fechamento do picker ou a confirmação do alerta secundário
        alert_btn = iframe.locator("button.alert-button:has-text('Confirmar')")
        picker = iframe.locator("ion-picker-cmp")
        start_time = time.time()
        while time.time() - start_time < 3.0:
            if alert_btn.is_visible():
                alert_btn.click()
                break
            if not picker.is_visible():
                break
            time.sleep(0.05)
        return True
    except:
        return False

def wait_for_new_list_and_items(iframe, previous_list_count, expected_non_zero=True, timeout_ms=10000):
    """
    Aguarda a abertura de uma nova lista de itens (ion-list) no iframe.
    Se expected_non_zero for True, aguarda até que a nova lista tenha pelo menos um item.
    """
    start_time = time.time()
    while time.time() - start_time < (timeout_ms / 1000.0):
        lists = iframe.locator("ion-list")
        current_count = lists.count()
        if current_count > previous_list_count:
            last_list = lists.last
            if expected_non_zero:
                items_count = last_list.locator("button.item-block, ion-item.item-block").count()
                if items_count > 0:
                    return True
            else:
                return True
        time.sleep(0.05)
    return False

def wait_for_list_close(iframe, previous_list_count, timeout_ms=5000):
    """
    Aguarda o fechamento de um modal/lista monitorando a redução de elementos 'ion-list'.
    """
    start_time = time.time()
    while time.time() - start_time < (timeout_ms / 1000.0):
        current_count = iframe.locator("ion-list").count()
        if current_count < previous_list_count:
            return True
        time.sleep(0.05)
    return False

def close_last_modal(iframe):
    """
    Fecha o último modal/lista aberto clicando no botão 'close' e aguarda seu fechamento.
    """
    lists_before_close = iframe.locator("ion-list").count()
    iframe.get_by_role("button", name="close").last.click()
    wait_for_list_close(iframe, lists_before_close)
