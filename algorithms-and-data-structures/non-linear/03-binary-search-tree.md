# Двоичное дерево поиска (BST)

**Предпосылки:** [бинарное дерево](02-binary-tree.md) (left/right, обходы — особенно in-order).

Линейный поиск по всем узлам занимает O(n). BST хранит элементы так, что поиск/вставка/удаление выполняются за O(h), где h — высота дерева. Если дерево близко к сбалансированному, h ≈ log₂(n); если вырождено — h ≈ n.

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

Главное следствие: **in-order обход BST даёт элементы в отсортированном порядке**. Для дерева выше: 1, 3, 4, 6, 7, 8, 10, 13, 14.

## Операции

**Поиск:** сравниваем искомое значение с текущим узлом и идём влево (если меньше) или вправо (если больше).

**Вставка:** ищем место как при поиске, вставляем новый узел туда, где путь заканчивается.

**Удаление:** зависит от количества детей. Если нет детей — просто удаляем. Если один ребёнок — заменяем узел его ребёнком. Если двое детей — находим successor (минимум справа) или predecessor (максимум слева), копируем значение, удаляем найденный узел.

## Сложность

| Операция | Лучший/средний | Худший |
|----------|----------------|--------|
| search | O(log n) | O(n) |
| insert | O(log n) | O(n) |
| delete | O(log n) | O(n) |

Худший случай — вырожденное дерево, когда все элементы выстроились в одну сторону (как связный список). Для гарантированного `O(log n)` используют самобалансирующиеся деревья (например, AVL или red-black).

## Реализация

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
end
```

BST даёт O(log n) в среднем, но вырожденное дерево превращается в список с O(n). Если задача — не произвольный поиск, а быстрый доступ к максимальному или минимальному элементу, есть структура с **гарантированным** O(log n) без риска вырождения: [куча](04-heap.md).
