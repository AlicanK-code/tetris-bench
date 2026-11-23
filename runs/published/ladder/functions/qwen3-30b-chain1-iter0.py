def count_holes(board):
    holes = 0
    for c in range(10):
        found_filled = False
        for r in range(20):
            if board[r][c]:
                found_filled = True
            elif found_filled:
                holes += 1
    return holes

def compute_sum_top(board):
    total = 0
    for c in range(10):
        top_r = 19
        for r in range(20):
            if board[r][c]:
                top_r = r
                break
        total += top_r
    return total

def score(board, placement):
    lines = placement["lines_cleared"]
    holes_count = count_holes(board)
    sum_top_val = compute_sum_top(board)
    column = placement["column"]
    rotation = placement["rotation"]
    
    return (lines * 100) - (holes_count * 10) + (sum_top_val * 5) + (column * 0.1) + (rotation * 0.01)
