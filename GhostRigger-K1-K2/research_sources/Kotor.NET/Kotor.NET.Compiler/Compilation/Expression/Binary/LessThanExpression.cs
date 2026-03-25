using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Binary
{
    public class LessThanExpression : IExpression
    {
        public IExpression LHS { get; set; }
        public IExpression RHS { get; set; }

        public LessThanExpression(IExpression lhs, IExpression rhs)
        {
            LHS = lhs;
            RHS = rhs;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            LHS.Compile(symbolTable, ncs);
            RHS.Compile(symbolTable, ncs);

            var lhs = LHS.GetDataType();
            var rhs = RHS.GetDataType();

            if (lhs == DataType.Int && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.LTII());
            }
            else if (lhs == DataType.Float && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.LTFF());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
