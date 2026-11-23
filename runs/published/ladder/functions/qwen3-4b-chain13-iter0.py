def compute_max_row(board):
    max_row = 0
    for i in range(20):
        for j in range(10):
            if board[i][j]:
                max_row = i
    return max_row

def compute_total_holes(board):
    total = 0
    for j in range(10):
        first_filled = None
        for i in range(20):
            if board[i][j]:
                first_filled = i
                break
        if first_filled is not None:
            for i in range(first_filled, 20):
                if not board[i][j]:
                    total += 1
    return total

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    max_row = compute_max_row(board)
    total_holes = compute_total_holes(board)
    return float(lines_cleared * 100 + 100 / (total_holes + 1) + 50 / (max_row + 1))
