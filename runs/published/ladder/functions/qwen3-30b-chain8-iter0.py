def compute_holes(board):
    holes = 0
    for j in range(10):
        has_filled = False
        for i in range(20):
            if board[i][j]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
    return holes

def compute_sum_top(board):
    total = 0
    for j in range(10):
        top_index = 20
        for i in range(20):
            if board[i][j]:
                top_index = i
                break
        total += top_index
    return total

def score(board, placement):
    lines = placement["lines_cleared"]
    holes = compute_holes(board)
    sum_top = compute_sum_top(board)
    rotation = placement["rotation"]
    return lines * 100 - holes * 5 + sum_top + rotation * 0.01
