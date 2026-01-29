# Куча (Heap)

**Предпосылки:** [бинарное дерево](02-binary-tree.md) (left/right, полнота), [массив](../linear/01-array.md) (индексация, формула адреса).

BST даёт O(log n) на поиск, вставку и удаление, но только в среднем случае — вырожденное дерево превращается в список с O(n). Если задача — не произвольный поиск, а быстрый доступ к максимальному (или минимальному) элементу, есть структура с гарантированным O(log n): **куча**.

## Heap: память vs структура данных

**Heap** в контексте памяти — область для динамически выделенных данных (противопоставляется стеку вызовов). **Heap** как структура данных — бинарное дерево с особым инвариантом. Между ними нет связи.

## Определение

Куча — бинарное дерево с двумя свойствами:

**Свойство кучи (heap property):** каждый родитель ≥ детей (max-heap) или ≤ детей (min-heap).

**Свойство формы (shape property):** дерево **полное** — все уровни заполнены, кроме последнего, который заполняется слева направо.

Свойство формы гарантирует высоту ≈ log₂(n) и позволяет хранить кучу в массиве без указателей:

```text
        90              Массив: [90, 60, 70, 30, 40, 50]
       /  \             Индекс:   0   1   2   3   4   5
      60   70
     / \   /
    30 40 50
```

Формулы навигации:

```ruby
left_child  = parent * 2 + 1
right_child = parent * 2 + 2
parent      = (child - 1) / 2
```

## Операции

**Вставка (sift up):** добавляем элемент в конец массива, затем пока элемент больше родителя — меняем местами с родителем. Сложность: O(log n).

**Извлечение максимума (sift down):** запоминаем корень (результат), перемещаем последний элемент на место корня, затем пока элемент меньше большего ребёнка — меняем местами с большим ребёнком. Сложность: O(log n).

**Просмотр максимума:** O(1) — просто возвращаем корень.

## Сравнение с другими структурами

| Структура | Добавить | Извлечь макс. |
|-----------|----------|---------------|
| Неотсорт. массив | O(1) | O(n) |
| Отсорт. массив | O(n) | O(1) |
| BST (средний) | O(log n) | O(log n) |
| BST (худший) | O(n) | O(n) |
| Куча | O(log n) | O(log n) |

Куча даёт **гарантированный** O(log n) без риска вырождения.

## Приоритетная очередь (Priority Queue)

Абстрактный тип данных с операциями: добавить элемент с приоритетом, извлечь элемент с наивысшим приоритетом. **Куча — эффективная реализация приоритетной очереди.** Max-heap для случая, когда больший приоритет = большее число. Min-heap — когда больший приоритет = меньшее число.

## Реализация

```ruby
class Heap
  def initialize
    @values = []
  end

  def peek
    @values[0]
  end

  def insert(value)
    @values << value
    sift_up
  end

  def extract_max
    maximum = peek
    last = @values.pop

    @values[0] = last unless maximum == last
    sift_down

    maximum
  end

  private

  def sift_up
    value = @values.last
    position = @values.size - 1
    parent_position, parent_value = parent(position)

    while parent_position >= 0 && parent_value < value
      @values[parent_position] = value
      @values[position] = parent_value
      position = parent_position
      parent_position, parent_value = parent(position)
    end
  end

  def sift_down
    value = @values.first
    position = 0
    child = biggest_child(position)

    return unless child

    while child && value < child[1]
      @values[position] = child[1]
      @values[child[0]] = value
      position = child[0]
      child = biggest_child(position)
    end
  end

  def parent(position)
    parent_pos = (position - 1) / 2
    [parent_pos, @values[parent_pos]]
  end

  def biggest_child(position)
    left = left_child(position)
    right = right_child(position)

    return if !left && !right
    return right unless left
    return left unless right

    [left, right].max { |l, r| l[1] <=> r[1] }
  end

  def left_child(position)
    l_position = position * 2 + 1
    value = @values[l_position]
    return unless value

    [l_position, value]
  end

  def right_child(position)
    r_position = position * 2 + 2
    value = @values[r_position]
    return unless value

    [r_position, value]
  end
end
```

## Max-heap vs Min-heap

Для превращения max-heap в min-heap нужно поменять сравнения и выбор ребёнка:
- в `sift_up`: менять местами, пока родитель **больше** ребёнка
- в `sift_down`: выбирать **меньшего** ребёнка и менять местами, пока родитель **больше** него

## Дубликаты

Куча допускает дубликаты. Инвариант "родитель ≥ детей" выполняется при равенстве (50 ≥ 50). При извлечении обе копии выйдут по очереди.
