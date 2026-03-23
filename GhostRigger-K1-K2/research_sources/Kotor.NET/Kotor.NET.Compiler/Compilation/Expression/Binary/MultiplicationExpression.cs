using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression
{
    public class MultiplicationExpression : IExpression
    {
        public IExpression LHS { get; set; }
        public IExpression RHS { get; set; }

        public MultiplicationExpression(IExpression lhs, IExpression rhs)
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
                ncs.Add(new NCSInstruction.MULII());
            }
            else if (lhs == DataType.Int && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.MULIF());
            }
            else if (lhs == DataType.Float && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.MULFI());
            }
            else if (lhs == DataType.Float && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.MULFF());
            }
            else if (lhs == DataType.Float && rhs == DataType.Vector)
            {
                ncs.Add(new NCSInstruction.MULFV());
            }
            else if (lhs == DataType.Vector && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.MULVF());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
