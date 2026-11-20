"""Имена событий элементов: английское имя карты → русское имя из палитры и синтакс-помощника. Одно место для досье (`brief.vocab`) и
`set_event` (русское имя события принимается наравне с английским)."""

EVENT_WORDS = {"OnChange": "ПриИзменении", "StartChoice": "НачалоВыбора", "ChoiceProcessing": "ОбработкаВыбора",
               "Clearing": "Очистка", "Opening": "Открытие", "TextEditEnd": "ОкончаниеВводаТекста",
               "AutoCompleteText": "АвтоПодборТекста", "StartListChoice": "НачалоВыбораИзСписка", "Tuning": "Регулирование",
               "Click": "Нажатие",
               # события табличного поля, списка и панели
               "Selection": "Выбор", "OnActivateRow": "ПриАктивизацииСтроки", "OnActivateColumn": "ПриАктивизацииКолонки",
               "OnActivateCell": "ПриАктивизацииЯчейки", "BeforeAddRow": "ПередНачаломДобавления",
               "BeforeRowChange": "ПередНачаломИзменения", "BeforeDeleteRow": "ПередУдалением", "OnStartEdit": "ПриНачалеРедактирования",
               "BeforeEditEnd": "ПередОкончаниемРедактирования", "OnCheckChange": "ПриИзмененииФлажка",
               "OnCurrentParentChange": "ПриСменеТекущегоРодителя", "OnRowOutput": "ПриВыводеСтроки", "ValueChoice": "ВыборЗначения",
               "OnEditEnd": "ПриОкончанииРедактирования", "NewObjectWriteProcessing": "ОбработкаЗаписиНовогоОбъекта",
               "AfterDeleteLine": "ПослеУдаления", "OnDataGet": "ПриПолученииДанных", "DragStart": "НачалоПеретаскивания",
               "DragCheck": "ПроверкаПеретаскивания", "DragEnd": "ОкончаниеПеретаскивания", "Drag": "Перетаскивание",
               "BeforeParentChange": "ПередСменойРодителя", "BeforeSetDeletionMark": "ПередУстановкойПометкиУдаления",
               "BeforeExpand": "ПередРазворачиванием", "BeforeCollapse": "ПередСворачиванием",
               "OnCurrentPageChange": "ПриСменеСтраницы", "OnActivateDate": "ПриАктивизацииДаты", "OnPeriodOutput": "ПриВыводеПериода",
               # события поля табличного документа (синтакс-помощник: «ПолеТабличногоДокумента» → События)
               "DetailProcessing": "ОбработкаРасшифровки", "OnActivate": "ПриАктивизации", "OnActivateArea": "ПриАктивизацииОбласти",
               "OnChangeAreaContent": "ПриИзмененииСодержимогоОбласти"}

ENGLISH_BY_RU = {ru: en for en, ru in EVENT_WORDS.items()}
