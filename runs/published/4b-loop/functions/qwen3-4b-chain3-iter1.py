def total_empty(board):
    return sum(1 for r in range(20) for c in range(10) if not board[r][c])

def max_col_height(board):
    return max(sum(1 for r in range(20) if board[r][c]) for c in range(10))

def min_col_height(board):
    return min(sum(1 for r in range(20) if board[r][c]) for c in range(10))

def surface_unevenness(board):
    col_heights = [sum(1 for r in range(20) if board[r][c]) for c in range(10)]
    return max(col_heights) - min(col_heights)

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    total_empty = total_empty(board)
    max_height = max_col_height(board)
    min_height = min_col_height(board)
    surface_unevenness_val = surface_unevenness(board)
    
    return lines_cleared * 100 + (20 - max_height) * 25 + (100 - total_empty) * 3 - surface_unevenness_val * 5
