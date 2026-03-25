using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression
{
    public class DivisionExpression : IExpression
    {
        public IExpression LHS { get; set; }
        public IExpression RHS { get; set; }

        public DivisionExpression(IExpression lhs, IExpression rhs)
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
                ncs.Add(new NCSInstruction.DIVII());
            }
            else if (lhs == DataType.Int && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.DIVIF());
            }
            else if (lhs == DataType.Float && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.DIVFI());
            }
            else if (lhs == DataType.Float && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.DIVFF());
            }
            else if (lhs == DataType.Float && rhs == DataType.Vector)
            {
                ncs.Add(new NCSInstruction.DIVFV());
            }
            else if (lhs == DataType.Vector && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.DIVVF());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
