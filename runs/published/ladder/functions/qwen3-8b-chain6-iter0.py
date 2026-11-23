def count_holes(board):
    total_holes = 0
    for col in range(10):
        filled_above = 0
        for row in range(20):
            if board[row][col]:
                filled_above += 1
            else:
                if filled_above > 0:
                    total_holes += 1
    return total_holes

def compute_max_row(board):
    max_row = 0
    for col in range(10):
        current_max = 0
        for row in range(20):
            if board[row][col]:
                current_max = row
        if current_max > max_row:
            max_row = current_max
    return max_row

def compute_unevenness(board):
    sum_diff = 0
    for i in range(19):
        row_i = sum(board[i][col] for col in range(10))
        row_i_plus_1 = sum(board[i+1][col] for col in range(10))
        sum_diff += abs(row_i - row_i_plus_1)
    return sum_diff

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    total_holes = count_holes(board)
    max_row = compute_max_row(board)
    unevenness = compute_unevenness(board)
    return float(lines_cleared * 1000 - total_holes * 10 - max_row - unevenness)
