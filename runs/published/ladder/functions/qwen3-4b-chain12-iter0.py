def score(board, placement):
    holes = 0
    for i in range(20):
        for j in range(10):
            if not board[i][j]:
                above = (i > 0) and board[i-1][j]
                below = (i < 19) and board[i+1][j]
                left = (j > 0) and board[i][j-1]
                right = (j < 9) and board[i][j+1]
                if above and below and left and right:
                    holes += 1
    max_min_row = 0
    for j in range(10):
        min_row = 20
        for i in range(20):
            if board[i][j]:
                if i < min_row:
                    min_row = i
        if min_row > max_min_row:
            max_min_row = min_row
    lines_cleared = placement["lines_cleared"]
    return float(lines_cleared * 10 + (20 - holes) * 5 + max_min_row * 2)
