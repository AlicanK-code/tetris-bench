def count_holes(board):
    holes = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                all_filled_above = True
                for r_above in range(r):
                    if not board[r_above][c]:
                        all_filled_above = False
                        break
                if all_filled_above:
                    holes += 1
    return holes

def max_column_height(board):
    max_height = 0
    for c in range(10):
        height = 0
        for r in range(20):
            if board[r][c]:
                height += 1
        if height > max_height:
            max_height = height
    return max_height

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    holes = count_holes(board)
    max_col_height = max_column_height(board)
    return lines_cleared * 100 + (100 - holes) * 30 + (20 - max_col_height) * 25
