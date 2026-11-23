def total_empty(board):
    return sum(1 for r in range(20) for c in range(10) if not board[r][c])

def max_col_height(board):
    return max(sum(1 for r in range(20) if board[r][c]) for c in range(10))

def surface_unevenness(board):
    col_heights = [sum(1 for r in range(20) if board[r][c]) for c in range(10)]
    return max(col_heights) - min(col_heights)

def bottom_empty(board):
    return sum(1 for r in (18, 19) for c in range(10) if not board[r][c])

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    total_empty = total_empty(board)
    max_height = max_col_height(board)
    surface_unevenness_val = surface_unevenness(board)
    bottom_empty_val = bottom_empty(board)
    
    return float(lines_cleared * 1000 - total_empty * 50 + (20 - max_height) * 25 - surface_unevenness_val * 15 - bottom_empty_val * 10)
