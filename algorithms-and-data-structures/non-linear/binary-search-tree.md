---
tags:
  - domain/algorithms
  - theme/indexing
  - theme/storage
  - type/concept
aliases:
  - BST
  - Binary Search Tree
order: 3
---

# Двоичное дерево поиска (BST)

**Предпосылки:** оценка сложности в O(…), [бинарное дерево](binary-tree.md) (left/right, обходы — особенно in-order).

Представим телефонную книгу на 10 000 контактов. Нужно быстро найти номер по имени, добавить новый контакт и удалить старый. Неотсортированный [массив](../linear/array.md) даёт O(1) на вставку, но O(n) на поиск — 10 000 сравнений для одного запроса. Отсортированный [массив](../linear/array.md) ускоряет поиск до O(log n) через бинарный поиск, но вставка требует сдвига O(n) элементов, чтобы не сломать порядок. [BST](binary-search-tree.md) совмещает оба преимущества: поиск, вставка и удаление выполняются за O(h), где h — высота [дерева](tree.md). Если [дерево](tree.md) близко к сбалансированному, h ≈ log₂(n) ≈ 14 для 10 000 контактов; если вырождено — h ≈ n.

## Инвариант

**Инвариант BST:** для каждого узла все значения в левом поддереве меньше значения узла, а все значения в правом поддереве — больше.

Ключи должны быть сравнимы (операции `<`/`>`). Правило для равных значений нужно выбрать заранее; в примере ниже дубликаты не добавляются.

```text
        8
       / \
      3   10
     / \    \
    1   6    14
       / \   /
      4   7 13
```

Главное следствие: **in-order обход [BST](binary-search-tree.md) даёт элементы в отсортированном порядке**. Для [дерева](tree.md) выше: 1, 3, 4, 6, 7, 8, 10, 13, 14.

## Операции

Инвариант позволяет на каждом шаге отбрасывать половину оставшихся узлов — все три операции опираются на это.

**Поиск:** сравниваем искомое значение с текущим узлом и идём влево (если меньше) или вправо (если больше).

**Вставка:** ищем место как при поиске, вставляем новый узел туда, где путь заканчивается.

**Удаление:** зависит от количества детей у удаляемого узла.

**Successor** (следующий по значению) — узел с наименьшим значением в правом поддереве. **Predecessor** (предыдущий по значению) — узел с наибольшим значением в левом поддереве. Оба находятся за O(h): спускаемся в соответствующее поддерево и идём до упора в противоположную сторону.

Случай 1 — нет детей (лист): просто удаляем узел.

Случай 2 — один ребёнок: заменяем узел его единственным ребёнком. Инвариант BST сохраняется, потому что все значения поддерева уже были по нужную сторону от родителя.

Случай 3 — двое детей: находим successor (минимум правого поддерева), копируем его значение в удаляемый узел, затем удаляем сам successor. Successor не может иметь левого ребёнка (иначе он не минимум), поэтому его удаление сводится к случаю 1 или 2.

```text
Удаляем 8:                     Successor = 10
        8                              10
       / \          →                 / \
      3   14                         3   14
         /                              /
        10                             13
          \
           13
```

## Сложность

Все три операции проходят путь от корня вниз, поэтому их сложность определяется высотой [дерева](tree.md).

| Операция | Лучший/средний | Худший |
|----------|----------------|--------|
| search | O(log n) | O(n) |
| insert | O(log n) | O(n) |
| delete | O(log n) | O(n) |

Худший случай — вырожденное [дерево](tree.md), когда все элементы выстроились в одну сторону (как [связный список](../linear/linked-list.md)). Если контакты в телефонной книге добавлялись по алфавиту — Alice, Bob, Charlie, Dave, … — каждый новый элемент уходит только вправо, и [дерево](tree.md) из 10 000 контактов превращается в цепочку высотой 10 000. Поиск деградирует до O(n) — не лучше неотсортированного [массива](../linear/array.md). Для гарантированного O(log n) используют самобалансирующиеся [деревья](tree.md) (например, AVL или red-black).

## Реализация

Ruby-реализация [BST](binary-search-tree.md) без балансировки — достаточна для понимания базовых операций:

```ruby
class Node
  attr_accessor :value, :left, :right

  def initialize(value)
    @value = value
    @left = nil
    @right = nil
  end
end

class BinarySearchTree
  def initialize
    @root = nil
  end

  def search(value)
    return nil unless @root

    current_node = @root

    while current_node && current_node.value != value do
      if value > current_node.value
        current_node = current_node.right
      else
        current_node = current_node.left
      end
    end

    current_node
  end

  def add(value)
    new_node = Node.new(value)
    return @root = new_node unless @root

    current_node = @root

    while current_node.value != value do
      bigger = value > current_node.value
      next_node = bigger ? current_node.right : current_node.left

      unless next_node
        if bigger
          current_node.right = new_node
        else
          current_node.left = new_node
        end
        return new_node
      end

      current_node = next_node
    end

    current_node
  end

  def delete(value)
    @root = delete_node(@root, value)
  end

  def in_order(&block)
    return enum_for(:in_order) unless block_given?
    return unless @root

    stack = [[@root, false]]

    until stack.empty? do
      node, already = stack.pop

      next yield node if !node.right && !node.left

      if already
        yield node
      else
        stack << [node.right, false] if node.right
        stack << [node, true]
        stack << [node.left, false] if node.left
      end
    end

    self
  end

  private

  def delete_node(node, value)
    return nil unless node

    if value < node.value
      node.left = delete_node(node.left, value)
    elsif value > node.value
      node.right = delete_node(node.right, value)
    else
      return node.right unless node.left
      return node.left unless node.right

      successor = node.right
      successor = successor.left while successor.left
      node.value = successor.value
      node.right = delete_node(node.right, successor.value)
    end

    node
  end
end
```

[BST](binary-search-tree.md) даёт O(log n) в среднем, но вырожденное [дерево](tree.md) превращается в [список](../linear/linked-list.md) с O(n). Для гарантированного O(log n) на произвольный поиск используют самобалансирующиеся [деревья](tree.md) (AVL, red-black). Но если задача уже — не произвольный поиск по ключу, а только быстро добавить элемент и извлечь максимальный (или минимальный), есть более простая структура с **гарантированным** O(log n) и без риска вырождения: [куча](heap.md).

Даже сбалансированное [BST](binary-search-tree.md) хранит один ключ в узле. В оперативной памяти это не проблема, но если представить «узел = отдельное чтение с диска», высота превращается в число операций ввода-вывода. При миллионе ключей высота порядка 20 (log₂ 10⁶ ≈ 20). [B-дерево](b-tree.md) решает эту проблему: один узел занимает целую страницу диска и хранит много ключей, поэтому глубина обычно получается порядка нескольких (часто 3–4).

## Sources

- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), 4th ed. (BST invariant, search/insert/delete, высота и сложность).

## Sources

- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), 4th ed. (BST invariant, search/insert/delete, высота и сложность).
